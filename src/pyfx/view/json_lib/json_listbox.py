"""
A :class:`urwid.ListBox` implementation specifically for rendering JSON
structure.
"""

import urwid
from loguru import logger
from overrides import overrides


class JSONListBox(urwid.ListBox):
    """
    A ListBox with special handling for navigation and collapsing of
    JSONWidgets.
    """

    def __init__(self, walker):
        # button number for `mouse_event`, there are 5 types of button
        # according to urwid docs and the number starts from 1
        self._last_press_button = 0
        self._keypress_handlers = {
            "up": self.move_focus_to_prev_line,
            "down": self.move_focus_to_next_line,
            "enter": self.toggle_collapse_on_focused_parent,
            "right": self.expand_focused_node,
            "left": self.collapse_focused_node,
            "e": self.expand_all,
            "c": self.collapse_all,
        }
        # Search state
        self._search_query = None
        self._last_search_position = None
        # set body to JSONListWalker
        super().__init__(walker)

    @overrides
    def keypress(self, size, key):
        (maxcol, maxrow) = size

        if self.set_focus_pending or self.set_focus_valign_pending:
            self._set_focus_complete((maxcol, maxrow), focus=True)

        focus_widget, pos = self._body.get_focus()
        if focus_widget is None:
            # empty listbox, can't do anything
            return key

        if focus_widget.selectable():
            key = focus_widget.keypress((maxcol,), key)
            if key is None:
                self.make_cursor_visible((maxcol, maxrow))
                return None

        if key in self._keypress_handlers:
            # Suppress warnings for unexpected arguments detected by PyCharm
            # for the handlers.
            # noinspection PyArgumentList
            self._keypress_handlers[key](size)
            return None

        return key

    @overrides
    def mouse_event(self, size, event, button, col, row, focus):
        """Handles mouse click to expand/collapse compose node."""
        if event == "mouse press":
            # remember last press button
            self._last_press_button = button
            return False

        if event != "mouse release" or self._last_press_button != 1:
            # only left mouse release
            self._last_press_button = 0
            return False
        # reset last press button
        self._last_press_button = 0

        focus_widget, pos = self._body.get_focus()
        if focus_widget is None:
            # empty listbox, can't do anything
            return False

        # For mouse event, because the widget may not be the current focused one
        # we need to calculate the position for the clicked one
        middle, top, bottom = self.calculate_visible(size, focus=True)

        if middle is None:
            # this should not happen and need to be look into.
            logger.info(
                f"{self}.calculate_visible({size}, True) returns " "middle as None"
            )
            return

        row_offset, focus_widget, focus_pos, focus_rows, cursor = middle
        bottom_top, fill_below = bottom
        trim_top, fill_above = top

        # fill_above is in bottom-up order
        fill_above.reverse()
        widget_list = fill_above + [(focus_widget, focus_pos, focus_rows)] + fill_below

        # Loops through the widgets list and find the clicked widget
        clicked_widget_row = -trim_top
        clicked_widget = None
        clicked_widget_pos = None
        for widget, widget_position, widget_rows in widget_list:
            if clicked_widget_row + widget_rows > row:
                clicked_widget = widget
                clicked_widget_pos = widget_position
                break
            clicked_widget_row += widget_rows

        if clicked_widget is None:
            return False

        if clicked_widget.selectable():
            self.change_focus(size, clicked_widget_pos, clicked_widget_row)

        if not clicked_widget.is_expandable():
            # TODO: call internal widget mouse_event here
            return False

        self.toggle_collapse_on_focused_parent(size)
        return True

    def expand_all(self, size):
        """Expands all the JSON nodes"""
        widget, position = self.get_focus()

        prev_widget, prev_position = widget, position
        while prev_widget is not None and prev_position is not None:

            if prev_widget.is_expandable() and (not prev_position.is_expanded()):
                prev_position.toggle_expanded()
                prev_position = prev_position.get_end_node()

            prev_widget, prev_position = self.body.get_prev(prev_position)

        next_widget, next_position = widget, position
        while next_widget is not None and next_position is not None:

            if next_widget.is_expandable() and (not next_position.is_expanded()):
                next_position.toggle_expanded()

            next_widget, next_position = self.body.get_next(next_position)

        self._invalidate()

    def collapse_all(self, size):
        """Collapses all JSON nodes"""
        widget, position = self.get_focus()

        prev_widget, prev_position = widget, position

        while prev_widget is not None and prev_position is not None:

            if prev_widget.is_expandable() and prev_position.is_expanded():
                # only JSONCompositeNode
                prev_position.collapse_all()

                if prev_position.is_end_node():
                    prev_position = prev_position.get_start_node()

            prev_widget, prev_position = self.body.get_prev(prev_position)

        next_widget, next_position = widget, position
        while next_widget is not None and next_position is not None:

            if next_widget.is_expandable() and next_position.is_expanded():
                next_position.collapse_all()

            next_widget, next_position = self.body.get_next(next_position)

        self.change_focus(size, position.get_root())

        self._invalidate()

    def toggle_collapse_on_focused_parent(self, size):
        """Toggles collapse on JSON `object` or `array` node"""

        widget, position = self.get_focus()
        if not widget.is_expandable():
            return

        if position.is_end_node():
            self.move_focus_from_end_node_to_start_node(size)

        position.toggle_expanded()
        self._invalidate()

    def _change_focus_maintaining_scroll(self, size, new_position, offset_adjustment=0):
        """Change focus to new_position while maintaining scroll position"""
        middle, top, bottom = self.calculate_visible(size, True)
        if middle is not None:
            row_offset, focus_widget, focus_pos, focus_rows, cursor = middle
            self.change_focus(size, new_position, row_offset + offset_adjustment)
        else:
            self.change_focus(size, new_position)

    def expand_focused_node(self, size):
        """Expands the focused node, or moves to first child if already expanded"""
        widget, position = self.get_focus()

        if not widget.is_expandable():
            return

        # If we're on an end node, move to start first
        if position.is_end_node():
            self.move_focus_from_end_node_to_start_node(size)
            widget, position = self.get_focus()

        # Expand if not already expanded
        if not position.is_expanded():
            position.toggle_expanded()
            self._invalidate()
        else:
            # Already expanded, move to first child
            first_child = position.get_first_child()
            if first_child is not None:
                # Get current widget height to position child below
                middle, top, bottom = self.calculate_visible(size, True)
                focus_rows = middle[3] if middle else 1
                self._change_focus_maintaining_scroll(size, first_child, focus_rows)

    def collapse_focused_node(self, size):
        """Collapses the focused node, or moves to parent if already collapsed"""
        widget, position = self.get_focus()

        # If we're on an end node, move to start node first
        if widget.is_expandable() and position.is_end_node():
            self.move_focus_from_end_node_to_start_node(size)
            widget, position = self.get_focus()

        # If this node is expandable and expanded, collapse it
        if widget.is_expandable() and position.is_expanded():
            position.toggle_expanded()
            self._invalidate()
        # Otherwise, move focus to the parent node if it exists
        elif position.get_parent() is not None:
            self._change_focus_maintaining_scroll(size, position.get_parent())

    def move_focus_from_end_node_to_start_node(self, size):
        """Moves focus from an end node to start node"""
        widget, position = self.get_focus()
        if not widget.is_expandable():
            return

        start_position = position.get_start_node()

        middle, top, bottom = self.calculate_visible(size, True)

        row_offset, focus_widget, focus_pos, focus_rows, cursor = middle
        trim_top, fill_above = top

        for fill in fill_above:

            widget, position, rows = fill

            if position == start_position:
                self.change_focus(size, position, row_offset - rows)
                return

            row_offset -= rows

        # start node is not visible in current frame, we have to scroll up
        # and set start node to the first line
        self.change_focus(size, start_position)

    def move_focus_to_prev_line(self, size):
        """Moves focus to previous line"""
        maxcol, maxrow = size

        widget, position = self.get_focus()

        prev_widget, prev_position = self._body.get_prev(position)

        if prev_position is None:
            return

        middle, top, bottom = self.calculate_visible(size, True)

        if middle is None:
            # this should not happen and need to be look into.
            logger.info(
                f"{self}.calculate_visible({size}, True) returns " "middle as None"
            )
            return

        row_offset, focus_widget, focus_pos, focus_rows, cursor = middle
        trim_top, fill_above = top

        # fetch the first widget above if exist
        if len(fill_above) > 0:
            widget, position, rows = fill_above[0]
            self.change_focus(size, position, row_offset - rows)
            return

        # must scroll since we at the first row of the current canvas
        self._invalidate()

        self.change_focus(size, prev_position, 0, "below")

    def move_focus_to_next_line(self, size):
        """Moves focus to next line"""
        maxcol, maxrow = size

        widget, position = self.get_focus()

        next_widget, next_position = self._body.get_next(position)

        if next_position is None:
            # still need to calculate visible, in case of expansion
            self.calculate_visible(size, True)
            return

        middle, top, bottom = self.calculate_visible(size, True)

        if middle is None:
            # this should not happen and need to be look into.
            logger.info(
                f"{self}.calculate_visible({size}, True) returns " "middle as None"
            )
            return

        row_offset, focus_widget, focus_pos, focus_rows, cursor = middle
        bottom_top, fill_below = bottom

        # fetch the first widget below
        if len(fill_below) > 0:
            widget, position, rows = fill_below[0]
            self.change_focus(size, position, row_offset + focus_rows)
            return

        # must scroll since we at the last row of the current canvas
        self._invalidate()

        self.change_focus(size, next_position, maxrow, "above")

    def _node_matches_search(self, position, query):
        """Check if a node's text representation contains the search query (case-insensitive)"""
        if not query:
            return False

        # Skip end nodes - they don't have searchable content
        if position.is_end_node():
            return False

        query_lower = query.lower()

        # Check the node's key
        if (
            hasattr(position, "get_key")
            and position.get_key()
            and query_lower in str(position.get_key()).lower()
        ):
            return True

        # Check the node's value representation
        if hasattr(position, "get_value"):
            value = position.get_value()
            if value is not None and query_lower in str(value).lower():
                return True

        return False

    def _expand_parents(self, position):
        """Expand all parent nodes of the given position"""
        parent = position.get_parent() if hasattr(position, "get_parent") else None
        while parent is not None:
            if hasattr(parent, "is_expanded") and not parent.is_expanded():
                parent.toggle_expanded()
            parent = parent.get_parent() if hasattr(parent, "get_parent") else None

    def search(self, query, forward=True):
        """Search for text in the JSON tree"""
        if not query:
            return False

        self._search_query = query
        widget, start_position = self.get_focus()

        if start_position is None:
            return False

        # Start searching from the next/previous position
        if forward:
            current_widget, current_position = self.body.get_next(start_position)
        else:
            current_widget, current_position = self.body.get_prev(start_position)

        # Search through all positions
        while current_position is not None:
            if self._node_matches_search(current_position, query):
                # Expand parent nodes to make the match visible
                self._expand_parents(current_position)
                self._invalidate()
                # Found a match, move to it
                self.set_focus(current_position)
                self._last_search_position = current_position
                return True

            # Move to next/prev position
            if forward:
                current_widget, current_position = self.body.get_next(current_position)
            else:
                current_widget, current_position = self.body.get_prev(current_position)

        # No match found, wrap around
        # Get the root position to start from the beginning/end
        root_position = start_position
        while (
            hasattr(root_position, "get_parent")
            and root_position.get_parent() is not None
        ):
            root_position = root_position.get_parent()

        if forward:
            # Start from the root
            current_widget, current_position = root_position.get_widget(), root_position
        else:
            # For backward search, start from root and go to the last position
            current_widget, current_position = root_position.get_widget(), root_position
            # Keep going next until we can't
            while True:
                next_widget, next_position = self.body.get_next(current_position)
                if next_position is None:
                    break
                current_widget, current_position = next_widget, next_position

        # Search from the beginning/end until we reach the start position
        while current_position is not None and current_position != start_position:
            if self._node_matches_search(current_position, query):
                # Expand parent nodes to make the match visible
                self._expand_parents(current_position)
                self._invalidate()
                self.set_focus(current_position)
                self._last_search_position = current_position
                return True

            if forward:
                current_widget, current_position = self.body.get_next(current_position)
            else:
                current_widget, current_position = self.body.get_prev(current_position)

        # No match found at all
        return False

    def search_next(self):
        """Find next match of the last search query"""
        if self._search_query:
            return self.search(self._search_query, forward=True)
        return False

    def search_prev(self):
        """Find previous match of the last search query"""
        if self._search_query:
            return self.search(self._search_query, forward=False)
        return False
