from dataclasses import dataclass
from enum import Enum

import urwid
from overrides import overrides

from pyfx.view.components.abstract_component_keys import BaseComponentKeyMapper
from pyfx.view.components.abstract_component_keys import KeyDefinition


class SearchBarKeys(KeyDefinition, Enum):
    """Enums for all the available keys defined in SearchBar."""

    SEARCH = "enter", "Find next match and return to JSON browser."
    CANCEL = "esc", "Exit search bar and return to JSON browser."


@dataclass(frozen=True)
class SearchBarKeyMapper(BaseComponentKeyMapper):
    search: str = "enter"
    cancel: str = "esc"

    @property
    @overrides
    def mapped_key(self):
        return {
            self.search: SearchBarKeys.SEARCH,
            self.cancel: SearchBarKeys.CANCEL
        }

    @property
    @overrides
    def short_help(self):
        return [f"SEARCH: {self.search}",
                f"CANCEL: {self.cancel}"]

    @property
    @overrides
    def detailed_help(self):
        keys = [self.search, self.cancel]
        descriptions = {key: self.mapped_key[key].description for key in keys}
        return {
            "section": "Search Bar",
            "description": descriptions
        }


class SearchBar(urwid.WidgetWrap):
    """The window to write search query."""

    SEARCH_PREFIX = "/"

    def __init__(self, mediator, keymapper, search_callback):
        self._mediator = mediator
        self._keymapper = keymapper
        self._search_callback = search_callback
        self._edit_widget = urwid.Edit()
        self._edit_widget.insert_text(SearchBar.SEARCH_PREFIX)
        super().__init__(self._edit_widget)

    def get_text(self):
        """Get the search text without the / prefix"""
        text = self._edit_widget.get_text()[0]
        if text.startswith(SearchBar.SEARCH_PREFIX):
            return text[len(SearchBar.SEARCH_PREFIX):]
        return text

    def clear(self):
        """Clear the search bar and reset to prefix"""
        self._edit_widget.set_edit_text(SearchBar.SEARCH_PREFIX)
        self._edit_widget.set_edit_pos(len(SearchBar.SEARCH_PREFIX))

    def help_message(self):
        return self._keymapper.short_help

    @overrides
    def keypress(self, size, key):
        key = self._keymapper.key(key)

        if key == SearchBarKeys.SEARCH.key:
            search_text = self.get_text()
            if search_text:  # Only search if there's actual text
                self._search_callback(search_text, forward=True)
            self._mediator.notify("search_bar", "show", "view_frame",
                                  "json_browser", True)
            return None

        if key == SearchBarKeys.CANCEL.key:
            self.clear()
            self._mediator.notify("search_bar", "show", "view_frame",
                                  "json_browser", True)
            return None

        # Handle other keys normally (typing)
        key = super().keypress(size, key)
        return key
