from overrides import overrides

from ..json_widget import JSONWidget


class ObjectUnexpandedWidget(JSONWidget):
    """The widget to display when an `object` type JSON node is not expanded."""

    def __init__(self, node, display_key):
        super().__init__(node, True, display_key)

    @overrides
    def load_value_markup(self):
        count = len(self._node.get_value())
        keys_text = "key" if count == 1 else "keys"
        return ["{\u2026}  ", ('json.count', f"// {count} {keys_text}")]
