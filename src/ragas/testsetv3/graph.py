import typing as t
import uuid

from graphene import Argument, Enum, Field, JSONString, List, ObjectType, Schema, String, InputObjectType

class NodeType(Enum):
    DOC = "doc"
    CHUNK = "chunk"

class NodeLevel(Enum):
    LEVEL_0 = 0
    LEVEL_1 = 1
    LEVEL_2 = 2

    def next_level(self) -> t.Optional["NodeLevel"]:
        level_values = list(NodeLevel)
        current_index = level_values.index(self)
        next_index = current_index + 1
        if next_index < len(level_values):
            return level_values[next_index]
        return None

class TargetFilter(InputObjectType):
    label = Argument(NodeType)
    property_key = String()
    property_value = String()
    comparison = String()

class Relationship(ObjectType):
    """Represents a directed relationship between two nodes in a graph."""

    id = String(required=True)
    source = Field(lambda: Node)
    target = Field(lambda: Node)
    label = String()
    properties = Field(JSONString)

    def __init__(self, id=None, **kwargs):
        if id is None:
            id = str(uuid.uuid4())
        super().__init__(id=id, **kwargs)

class Node(ObjectType):
    """Represents a node in a graph with associated properties."""

    id = String(required=True)
    label = Field(NodeType)
    properties = Field(JSONString)
    relationships = List(
        lambda: Relationship,
        label=Argument(String),
        property_key=Argument(String),
        property_value=Argument(String),
        comparison=Argument(String),
        target_filter=Argument(TargetFilter)  # New argument to filter by target properties
    )
    level = Field(NodeLevel)

    def __init__(self, id=None, **kwargs):
        if id is None:
            id = str(uuid.uuid4())
        super().__init__(id=id, **kwargs)

    def resolve_relationships(
        self, info, label=None, property_key=None, property_value=None, comparison=None, target_filter=None
    ):
        relationships = info.context.get("relationships", [])
        filtered_relationships = [
            rel for rel in relationships if rel.source.id == self.id
        ]

        if label:
            filtered_relationships = [
                rel for rel in filtered_relationships if rel.label == label
            ]

        if property_key and property_value:
            if comparison == "gt":
                filtered_relationships = [
                    rel
                    for rel in filtered_relationships
                    if rel.properties
                    and property_key in rel.properties
                    and float(rel.properties[property_key]) > float(property_value)
                ]
            elif comparison == "lt":
                filtered_relationships = [
                    rel
                    for rel in filtered_relationships
                    if rel.properties
                    and property_key in rel.properties
                    and float(rel.properties[property_key]) < float(property_value)
                ]
            elif comparison == "eq":
                filtered_relationships = [
                    rel
                    for rel in filtered_relationships
                    if rel.properties
                    and property_key in rel.properties
                    and rel.properties[property_key] == property_value
                ]
            else:
                raise ValueError(f"Invalid comparison operator: {comparison}")

        if target_filter:
            target_label = target_filter.get('label')
            target_property_key = target_filter.get('property_key')
            target_property_value = target_filter.get('property_value')
            target_comparison = target_filter.get('comparison')

            filtered_relationships = [
                rel for rel in filtered_relationships if (
                    (not target_label or rel.target.label == target_label) and
                    (not target_property_key or (
                        target_property_key in rel.target.properties and
                        (
                            (target_comparison == "gt" and float(rel.target.properties[target_property_key]) > float(target_property_value)) or
                            (target_comparison == "lt" and float(rel.target.properties[target_property_key]) < float(target_property_value)) or
                            (target_comparison == "eq" and rel.target.properties[target_property_key] == target_property_value)
                        )
                    ))
                )
            ]

        return filtered_relationships

class Query(ObjectType):
    filter_nodes = List(
        Node,
        ids=Argument(List(String)),
        label=Argument(NodeType),
        level=Argument(NodeLevel),
        property_key=Argument(String),
        property_value=Argument(String),
    )

    def resolve_filter_nodes(
        parent,
        info,
        ids=None,
        label=None,
        level=None,
        property_key=None,
        property_value=None,
    ):
        nodes = info.context.get("nodes", [])
        filtered_nodes = nodes

        if ids:
            if isinstance(ids, list):
                filtered_nodes = [node for node in nodes if node.id in ids]
            else:
                filtered_nodes = [node for node in nodes if node.id == id]

        if label:
            filtered_nodes = [node for node in nodes if node.label == label]

        if level:
            filtered_nodes = [node for node in nodes if node.level == level]

        if property_key and property_value:
            filtered_nodes = [
                node
                for node in filtered_nodes
                if node.properties
                and node.properties.get(property_key) == property_value
            ]

        return filtered_nodes

schema = Schema(query=Query)
