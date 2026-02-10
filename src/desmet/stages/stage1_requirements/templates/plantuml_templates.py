"""
PlantUML Templates for Requirements Stage

Provides templates and generators for creating PlantUML diagrams
from structured requirement data.
"""

from typing import Optional


class PlantUMLTemplates:
    """Collection of PlantUML template generators."""

    @staticmethod
    def use_case_diagram(
        title: str,
        actors: list[dict],
        use_cases: list[dict],
        relationships: list[dict] = None
    ) -> str:
        """
        Generate a Use Case Diagram.

        Args:
            title: Diagram title
            actors: List of {name, type} dicts
            use_cases: List of {id, name, package} dicts
            relationships: List of {from, to, type} dicts (type: uses, extends, includes)
        """
        lines = [
            "@startuml",
            f"title {title}",
            "",
            "left to right direction",
            "skinparam packageStyle rectangle",
            "",
        ]

        # Add actors
        for actor in actors:
            actor_type = actor.get('type', 'primary')
            if actor_type == 'external_system':
                lines.append(f'actor "{actor["name"]}" as {actor["name"].replace(" ", "_")} <<system>>')
            else:
                lines.append(f'actor "{actor["name"]}" as {actor["name"].replace(" ", "_")}')

        lines.append("")

        # Group use cases by package
        packages = {}
        for uc in use_cases:
            pkg = uc.get('package', 'System')
            if pkg not in packages:
                packages[pkg] = []
            packages[pkg].append(uc)

        for pkg_name, pkg_use_cases in packages.items():
            lines.append(f'rectangle "{pkg_name}" {{')
            for uc in pkg_use_cases:
                uc_id = uc['id'].replace('-', '_')
                lines.append(f'  usecase "{uc["name"]}" as {uc_id}')
            lines.append("}")
            lines.append("")

        # Add relationships
        if relationships:
            for rel in relationships:
                from_id = rel['from'].replace('-', '_').replace(' ', '_')
                to_id = rel['to'].replace('-', '_').replace(' ', '_')
                rel_type = rel.get('type', 'uses')

                if rel_type == 'includes':
                    lines.append(f'{from_id} ..> {to_id} : <<include>>')
                elif rel_type == 'extends':
                    lines.append(f'{from_id} ..> {to_id} : <<extend>>')
                else:
                    lines.append(f'{from_id} --> {to_id}')

        lines.append("")
        lines.append("@enduml")
        return "\n".join(lines)

    @staticmethod
    def class_diagram(
        title: str,
        classes: list[dict],
        relationships: list[dict] = None,
        packages: dict = None
    ) -> str:
        """
        Generate a Class Diagram.

        Args:
            title: Diagram title
            classes: List of {name, attributes, methods, stereotype} dicts
            relationships: List of {from, to, type, label, cardinality} dicts
            packages: Dict of {package_name: [class_names]}
        """
        lines = [
            "@startuml",
            f"title {title}",
            "",
            "skinparam classAttributeIconSize 0",
            "",
        ]

        # Helper to format class
        def format_class(cls: dict) -> list[str]:
            cls_lines = []
            stereotype = cls.get('stereotype', '')
            stereotype_str = f" <<{stereotype}>>" if stereotype else ""

            cls_lines.append(f'class "{cls["name"]}"{stereotype_str} {{')

            # Attributes
            for attr in cls.get('attributes', []):
                visibility = attr.get('visibility', '+')
                attr_type = attr.get('type', 'String')
                attr_name = attr.get('name', 'unknown')
                cls_lines.append(f'  {visibility}{attr_name}: {attr_type}')

            # Separator if both attributes and methods exist
            if cls.get('attributes') and cls.get('methods'):
                cls_lines.append('  --')

            # Methods
            for method in cls.get('methods', []):
                visibility = method.get('visibility', '+')
                return_type = method.get('return_type', 'void')
                method_name = method.get('name', 'unknown')
                params = method.get('parameters', '')
                cls_lines.append(f'  {visibility}{method_name}({params}): {return_type}')

            cls_lines.append('}')
            return cls_lines

        # Add classes (with optional packaging)
        if packages:
            for pkg_name, pkg_classes in packages.items():
                lines.append(f'package "{pkg_name}" {{')
                for cls in classes:
                    if cls['name'] in pkg_classes:
                        lines.extend(['  ' + l for l in format_class(cls)])
                lines.append('}')
                lines.append('')
        else:
            for cls in classes:
                lines.extend(format_class(cls))
                lines.append('')

        # Add relationships
        if relationships:
            lines.append('')
            for rel in relationships:
                from_cls = rel['from'].replace(' ', '')
                to_cls = rel['to'].replace(' ', '')
                rel_type = rel.get('type', 'association')
                label = rel.get('label', '')
                cardinality = rel.get('cardinality', '')

                label_str = f' : {label}' if label else ''
                card_str = f' "{cardinality}"' if cardinality else ''

                if rel_type == 'inheritance':
                    lines.append(f'{from_cls} --|> {to_cls}')
                elif rel_type == 'implementation':
                    lines.append(f'{from_cls} ..|> {to_cls}')
                elif rel_type == 'composition':
                    lines.append(f'{from_cls} *-- {to_cls}{card_str}{label_str}')
                elif rel_type == 'aggregation':
                    lines.append(f'{from_cls} o-- {to_cls}{card_str}{label_str}')
                elif rel_type == 'dependency':
                    lines.append(f'{from_cls} ..> {to_cls}{label_str}')
                else:
                    lines.append(f'{from_cls} -- {to_cls}{card_str}{label_str}')

        lines.append('')
        lines.append('@enduml')
        return '\n'.join(lines)

    @staticmethod
    def sequence_diagram(
        title: str,
        participants: list[dict],
        messages: list[dict],
        notes: list[dict] = None
    ) -> str:
        """
        Generate a Sequence Diagram.

        Args:
            title: Diagram title
            participants: List of {name, type, alias} dicts
            messages: List of {from, to, message, type} dicts
            notes: List of {position, participant, text} dicts
        """
        lines = [
            "@startuml",
            f"title {title}",
            "",
            "autonumber",
            "",
        ]

        # Add participants
        for p in participants:
            p_type = p.get('type', 'participant')
            alias = p.get('alias', p['name'].replace(' ', '_'))
            if p_type == 'actor':
                lines.append(f'actor "{p["name"]}" as {alias}')
            elif p_type == 'database':
                lines.append(f'database "{p["name"]}" as {alias}')
            elif p_type == 'queue':
                lines.append(f'queue "{p["name"]}" as {alias}')
            elif p_type == 'boundary':
                lines.append(f'boundary "{p["name"]}" as {alias}')
            elif p_type == 'control':
                lines.append(f'control "{p["name"]}" as {alias}')
            elif p_type == 'entity':
                lines.append(f'entity "{p["name"]}" as {alias}')
            else:
                lines.append(f'participant "{p["name"]}" as {alias}')

        lines.append('')

        # Add messages
        for msg in messages:
            from_p = msg['from'].replace(' ', '_')
            to_p = msg['to'].replace(' ', '_')
            msg_type = msg.get('type', 'sync')
            message = msg.get('message', '')

            if msg_type == 'async':
                lines.append(f'{from_p} ->> {to_p}: {message}')
            elif msg_type == 'return':
                lines.append(f'{from_p} --> {to_p}: {message}')
            elif msg_type == 'self':
                lines.append(f'{from_p} -> {from_p}: {message}')
            elif msg_type == 'create':
                lines.append(f'{from_p} -> {to_p} **: {message}')
            elif msg_type == 'destroy':
                lines.append(f'{from_p} -> {to_p} !!: {message}')
            else:
                lines.append(f'{from_p} -> {to_p}: {message}')

        # Add notes
        if notes:
            lines.append('')
            for note in notes:
                position = note.get('position', 'right of')
                participant = note['participant'].replace(' ', '_')
                text = note['text']
                lines.append(f'note {position} {participant}: {text}')

        lines.append('')
        lines.append('@enduml')
        return '\n'.join(lines)

    @staticmethod
    def component_diagram(
        title: str,
        components: list[dict],
        interfaces: list[dict] = None,
        connections: list[dict] = None,
        packages: dict = None
    ) -> str:
        """
        Generate a Component Diagram.

        Args:
            title: Diagram title
            components: List of {name, stereotype, description} dicts
            interfaces: List of {name, component} dicts
            connections: List of {from, to, interface, label} dicts
            packages: Dict of {package_name: [component_names]}
        """
        lines = [
            "@startuml",
            f"title {title}",
            "",
            "skinparam componentStyle rectangle",
            "",
        ]

        def format_component(comp: dict) -> str:
            stereotype = comp.get('stereotype', '')
            stereotype_str = f" <<{stereotype}>>" if stereotype else ""
            return f'component "{comp["name"]}"{stereotype_str}'

        # Add components (with optional packaging)
        if packages:
            for pkg_name, pkg_components in packages.items():
                lines.append(f'package "{pkg_name}" {{')
                for comp in components:
                    if comp['name'] in pkg_components:
                        lines.append(f'  {format_component(comp)}')
                lines.append('}')
                lines.append('')
        else:
            for comp in components:
                lines.append(format_component(comp))

        # Add interfaces
        if interfaces:
            lines.append('')
            for iface in interfaces:
                comp_name = iface['component'].replace(' ', '_')
                iface_name = iface['name'].replace(' ', '_')
                lines.append(f'interface "{iface["name"]}" as {iface_name}')
                lines.append(f'{comp_name} - {iface_name}')

        # Add connections
        if connections:
            lines.append('')
            for conn in connections:
                from_c = conn['from'].replace(' ', '_')
                to_c = conn['to'].replace(' ', '_')
                label = conn.get('label', '')
                label_str = f' : {label}' if label else ''

                if conn.get('interface'):
                    iface = conn['interface'].replace(' ', '_')
                    lines.append(f'{from_c} --> {iface}')
                else:
                    lines.append(f'{from_c} --> {to_c}{label_str}')

        lines.append('')
        lines.append('@enduml')
        return '\n'.join(lines)

    @staticmethod
    def activity_diagram(
        title: str,
        activities: list[dict],
        transitions: list[dict],
        swimlanes: dict = None
    ) -> str:
        """
        Generate an Activity Diagram.

        Args:
            title: Diagram title
            activities: List of {id, name, type} dicts (type: action, decision, fork, join, start, end)
            transitions: List of {from, to, guard} dicts
            swimlanes: Dict of {lane_name: [activity_ids]}
        """
        lines = [
            "@startuml",
            f"title {title}",
            "",
        ]

        if swimlanes:
            for lane_name, activity_ids in swimlanes.items():
                lines.append(f'|{lane_name}|')
                for act in activities:
                    if act['id'] in activity_ids:
                        act_type = act.get('type', 'action')
                        if act_type == 'start':
                            lines.append('start')
                        elif act_type == 'end':
                            lines.append('stop')
                        elif act_type == 'decision':
                            lines.append(f'if ({act["name"]}) then (yes)')
                        else:
                            lines.append(f':{act["name"]};')
        else:
            lines.append('start')
            for act in activities:
                act_type = act.get('type', 'action')
                if act_type == 'decision':
                    lines.append(f'if ({act["name"]}) then (yes)')
                elif act_type == 'end':
                    lines.append('stop')
                elif act_type != 'start':
                    lines.append(f':{act["name"]};')

        lines.append('')
        lines.append('@enduml')
        return '\n'.join(lines)

    @staticmethod
    def entity_relationship_diagram(
        title: str,
        entities: list[dict],
        relationships: list[dict]
    ) -> str:
        """
        Generate an Entity Relationship Diagram.

        Args:
            title: Diagram title
            entities: List of {name, attributes} dicts where attributes is [{name, type, pk, fk}]
            relationships: List of {from, to, type, label, from_cardinality, to_cardinality} dicts
        """
        lines = [
            "@startuml",
            f"title {title}",
            "",
            "skinparam linetype ortho",
            "",
        ]

        # Add entities
        for entity in entities:
            lines.append(f'entity "{entity["name"]}" {{')
            for attr in entity.get('attributes', []):
                prefix = ''
                if attr.get('pk'):
                    prefix = '* '
                elif attr.get('fk'):
                    prefix = '# '

                attr_type = attr.get('type', 'String')
                lines.append(f'  {prefix}{attr["name"]}: {attr_type}')
            lines.append('}')
            lines.append('')

        # Add relationships
        for rel in relationships:
            from_e = rel['from'].replace(' ', '_')
            to_e = rel['to'].replace(' ', '_')
            from_card = rel.get('from_cardinality', '1')
            to_card = rel.get('to_cardinality', '*')
            label = rel.get('label', '')

            # Map cardinality symbols
            card_map = {
                '1': '||',
                '0..1': '|o',
                '*': '}|',
                '0..*': '}o',
                '1..*': '}|'
            }
            from_sym = card_map.get(from_card, '||')
            to_sym = card_map.get(to_card, '}|')

            label_str = f' : {label}' if label else ''
            lines.append(f'{from_e} {from_sym}--{to_sym} {to_e}{label_str}')

        lines.append('')
        lines.append('@enduml')
        return '\n'.join(lines)

    @staticmethod
    def state_diagram(
        title: str,
        states: list[dict],
        transitions: list[dict]
    ) -> str:
        """
        Generate a State Diagram.

        Args:
            title: Diagram title
            states: List of {name, type, description} dicts (type: state, initial, final, composite)
            transitions: List of {from, to, trigger, guard, action} dicts
        """
        lines = [
            "@startuml",
            f"title {title}",
            "",
        ]

        # Add states
        for state in states:
            state_type = state.get('type', 'state')
            state_name = state['name'].replace(' ', '_')

            if state_type == 'initial':
                lines.append(f'[*] --> {state_name}')
            elif state_type == 'final':
                pass  # handled in transitions
            elif state_type == 'composite':
                lines.append(f'state "{state["name"]}" as {state_name} {{')
                for sub in state.get('substates', []):
                    lines.append(f'  state "{sub}"')
                lines.append('}')
            else:
                desc = state.get('description', '')
                if desc:
                    lines.append(f'state "{state["name"]}" as {state_name} : {desc}')
                else:
                    lines.append(f'state "{state["name"]}" as {state_name}')

        lines.append('')

        # Add transitions
        for trans in transitions:
            from_s = trans['from'].replace(' ', '_')
            to_s = trans['to'].replace(' ', '_')

            if from_s == '[*]':
                from_s = '[*]'
            if to_s == '[*]':
                to_s = '[*]'

            label_parts = []
            if trans.get('trigger'):
                label_parts.append(trans['trigger'])
            if trans.get('guard'):
                label_parts.append(f'[{trans["guard"]}]')
            if trans.get('action'):
                label_parts.append(f'/ {trans["action"]}')

            label = ' '.join(label_parts)
            label_str = f' : {label}' if label else ''

            lines.append(f'{from_s} --> {to_s}{label_str}')

        lines.append('')
        lines.append('@enduml')
        return '\n'.join(lines)
