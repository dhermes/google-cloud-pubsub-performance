import pydot


class Tree(object):

    def __init__(self, name, parent, weight=1):
        # name: str
        # parent: Optional[Tree]
        self.name = name
        self.parent = parent
        # children: Tuple[Tree]
        self.children = ()
        # weight: int
        self.weight = 1

    @property
    def size(self):
        # Returns: int
        result = 1  # Count self.
        for child in self.children:
            result += child.size
        return result

    def get(self, name):
        # name: str
        # Returns: Optional[Tree]
        # Raises: RuntimeError
        if name == self.name:
            return self

        matches = []
        for child in self.children:
            match = child.get(name)
            if match is not None:
                matches.append(match)

        if len(matches) == 0:
            return None
        elif len(matches) == 1:
            return matches[0]
        else:
            raise RuntimeError('Too many matches', matches)

    def add_child(self, name):
        # name: str
        new_node = Tree(name, self)
        self.children += (new_node,)

    def is_same(self, node):
        # node: Tree
        name1 = clean_name(self.name)
        name2 = clean_name(node.name)
        if name1 != name2:
            return False

        if len(self.children) != len(node.children):
            return False

        for child1, child2 in zip(self.children, node.children):
            if not child1.is_same(child2):
                return False

        return True

    def collapse(self):
        uniques = []
        for child in self.children:
            matched = []
            for existing in uniques:
                if child.is_same(existing):
                    matched.append(existing)

            if len(matched) == 0:
                uniques.append(child)
            elif len(matched) == 1:
                matched[0].weight += 1
            else:
                raise RuntimeError('Too many matches', matches)

        self.children = tuple(uniques)
        for child in self.children:
            child.collapse()

    def pydot(self, names=None):
        if names is None:
            names = set()

        if self.parent is None:
            graph = pydot.Dot()
        else:
            graph = pydot.Subgraph()

        subgraphs = []
        edges = []
        for child in self.children:
            subgraphs.append(child.pydot(names=names))
            names.update((self.name, child.name))
            edge = pydot.Edge(
                self.name,
                child.name,
            )
            if child.weight != 1:
                edge.obj_dict['attributes']['label'] = str(child.weight)
            edges.append(edge)

        for subgraph in subgraphs:
            graph.add_subgraph(subgraph)

        for edge in edges:
            graph.add_edge(edge)

        if self.parent is None:
            for name in names:
                stripped_name = clean_name(name)
                if stripped_name != name:
                    node = pydot.Node(name)
                    node.obj_dict['attributes']['label'] = stripped_name
                    graph.add_node(node)

        return graph

    def save_graphviz(self, filename_base):
        self.collapse()

        graph = self.pydot()

        filename_dot = '{}.dot'.format(filename_base)
        with open(filename_dot, 'w') as file_obj:
            file_obj.write(graph.to_string())
        print('Created {}'.format(filename_dot))

        filename_svg = '{}.svg'.format(filename_base)
        with open(filename_svg, 'wb') as file_obj:
            file_obj.write(graph.create_svg())
        print('Created {}'.format(filename_svg))


def clean_name(name):
    result = name.rstrip('+')
    if result[:7] == 'Thread-':
        result = result[7:]
    return result
