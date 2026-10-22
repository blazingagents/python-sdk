"""Every property of every response the SDK decodes maps to a model field."""

from __future__ import annotations

import json
import types
from typing import Annotated, Any, Literal, Union, get_args, get_origin, get_type_hints

from pydantic import BaseModel
from test_contract_scope import NOT_FOUND, SPEC, SURFACES, contract, observe, resolve

from blazing_agents import BlazingAgents

Schema = dict[str, Any]
DOCUMENT: Schema = json.loads(SPEC.read_text())


def resolved(schema: Schema) -> Schema:
    while "$ref" in schema:
        schema = DOCUMENT["components"]["schemas"][schema["$ref"].split("/")[-1]]
    return schema


def branches(schema: Schema) -> list[Schema]:
    """The object or array shapes a schema allows, with composition expanded."""
    schema = resolved(schema)
    for key in ("anyOf", "oneOf"):
        if key in schema:
            return [shape for branch in schema[key] for shape in branches(branch)]
    if "allOf" in schema:
        merged: Schema = {"type": "object", "properties": {}}
        for part in schema["allOf"]:
            for shape in branches(part):
                merged["properties"] |= shape.get("properties", {})
        return [merged]
    return [schema]


def members(annotation: object) -> list[object]:
    """The types an annotation allows, with Annotated, unions and aliases unwrapped."""
    annotation = getattr(annotation, "__value__", annotation)
    origin = get_origin(annotation)
    if origin is Annotated:
        return members(get_args(annotation)[0])
    if origin in (Union, types.UnionType):
        return [member for arg in get_args(annotation) for member in members(arg)]
    return [annotation]


def models(annotation: object) -> list[type[BaseModel]]:
    return [
        member
        for member in members(annotation)
        if isinstance(member, type) and issubclass(member, BaseModel)
    ]


def item_types(annotation: object) -> list[object]:
    return [
        get_args(member)[0]
        for member in members(annotation)
        if get_origin(member) in (list, tuple) and get_args(member)
    ]


def aliases(model: type[BaseModel]) -> dict[str, object]:
    return {
        field.alias or name: field.annotation
        for name, field in model.model_fields.items()
    }


def discriminator(shape: Schema) -> tuple[str, object] | None:
    for name, prop in shape.get("properties", {}).items():
        prop = resolved(prop)
        if "const" in prop:
            return name, prop["const"]
        if len(prop.get("enum", ())) == 1:
            return name, prop["enum"][0]
    return None


def counterpart(shape: Schema, candidates: list[type[BaseModel]]) -> type[BaseModel]:
    """The candidate model for an object shape: by discriminator, else best overlap."""
    if (tag := discriminator(shape)) and len(candidates) > 1:
        name, value = tag
        for model in candidates:
            field = aliases(model).get(name)
            if field is not None and any(
                get_origin(member) is Literal and value in get_args(member)
                for member in members(field)
            ):
                return model
    properties = shape.get("properties", {}).keys()
    return max(candidates, key=lambda model: len(properties & aliases(model).keys()))


def missing(schema: Schema, annotation: object, where: str) -> list[tuple[str, str]]:
    """(where, "Model.property") for each property annotation has no field for."""
    problems: list[tuple[str, str]] = []
    for shape in branches(schema):
        if shape.get("type") == "array" and "items" in shape:
            for item in item_types(annotation):
                problems += missing(shape["items"], item, f"{where}[]")
            continue
        candidates = models(annotation)
        properties: Schema = shape.get("properties", {})
        if not candidates or not properties:
            continue
        model = counterpart(shape, candidates)
        fields = aliases(model)
        for name, prop in properties.items():
            if name not in fields:
                problems.append((where, f"{model.__name__}.{name}"))
            else:
                problems += missing(prop, fields[name], f"{where}.{name}")
    return problems


def response_schema(operation_id: str) -> Schema | None:
    """The JSON schema of the operation's success response, if it has one."""
    spec = next(
        spec
        for methods in DOCUMENT["paths"].values()
        for spec in methods.values()
        if spec.get("operationId") == operation_id
    )
    for status, response in spec["responses"].items():
        content: Schema = response.get("content", {})
        schema: Schema | None = content.get("application/json", {}).get("schema")
        if status.startswith("2") and schema is not None:
            return schema
    return None


def method_at(client: object, path: str) -> object:
    target = client
    for part in path.split("."):
        target = (
            getattr(target, part.removesuffix("()"))("ag_0123456789abcdef")
            if part.endswith("()")
            else getattr(target, part)
        )
    return target


def decoded_responses() -> dict[tuple[str, str], tuple[Schema, object]]:
    """The response schema and return annotation of each method decoding a model."""
    operations = contract()
    sent = observe(SURFACES["tenant"], False, NOT_FOUND).sent
    pairs: dict[tuple[str, str], tuple[Schema, object]] = {}
    with BlazingAgents(api_key="ba_test", base_url="https://api.test") as client:
        for method, requests in sent.items():
            returned = get_type_hints(method_at(client, method)).get("return")
            if not models(returned) and not any(map(models, item_types(returned))):
                continue
            for request in requests:
                operation = resolve(operations, request)
                assert operation is not None
                assert operation.id is not None
                schema = response_schema(operation.id)
                assert schema is not None, f"{method}: {operation} has no JSON body"
                pairs[method, operation.id] = (schema, returned)
    return pairs


def test_every_response_property_maps_to_a_model_field() -> None:
    pairs = decoded_responses()
    assert pairs
    found = [
        problem
        for (method, operation_id), (schema, returned) in sorted(pairs.items())
        for problem in missing(schema, returned, f"{method} ({operation_id})")
    ]
    unmapped = [f"{where}: {path}" for where, path in found]
    assert not unmapped, "Response properties with no model field:\n" + "\n".join(
        unmapped
    )
