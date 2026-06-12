"""Digital Twins tab controller bound to widgets in main_window.ui."""

from qgis.PyQt import QtWidgets
from qgis.PyQt.QtCore import QObject, Qt, QUrl, pyqtSignal
from qgis.PyQt.QtGui import QPixmap
from qgis.PyQt.QtNetwork import QNetworkAccessManager, QNetworkRequest
from qgis.PyQt.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

# PyQt enum compatibility (QGIS 4 / PyQt6, with PyQt5 fallback names).
NO_SELECTION_MODE = getattr(
    QtWidgets.QAbstractItemView, "SelectionMode", QtWidgets.QAbstractItemView
).NoSelection
CHECKED_STATE = getattr(Qt, "CheckState", Qt).Checked
UNCHECKED_STATE = getattr(Qt, "CheckState", Qt).Unchecked
USER_ROLE = getattr(Qt, "ItemDataRole", Qt).UserRole
ITEM_IS_USER_CHECKABLE = getattr(Qt, "ItemFlag", Qt).ItemIsUserCheckable
ARROW_RIGHT = getattr(Qt, "ArrowType", Qt).RightArrow
ARROW_DOWN = getattr(Qt, "ArrowType", Qt).DownArrow
ALIGN_CENTER = getattr(Qt, "AlignmentFlag", Qt).AlignCenter


class DigitalTwinsTab(QObject):
    digital_twin_load_requested = pyqtSignal(str)

    LOAD_BUTTON_TEXT = "Load Digital Twin"
    CLEAR_FILTERS_TEXT = "Clear filters"

    def __init__(self, tab_widget):
        super().__init__(tab_widget)
        self.tab_widget = tab_widget

        self.current_page = 0
        self.page_size = 20
        self.total_count = 0
        self.prev_button = None
        self.next_button = None
        self.page_label = None
        self._network_manager = QNetworkAccessManager(self)
        self._image_requests = {}
        self._network_manager.finished.connect(self._on_preview_image_loaded)

        self._all_digital_twins = []
        self._selected_filters = {
            "owner_hubs": set(),
            "findability": set(),
        }

        self._main_layout = self.tab_widget.findChild(QtWidgets.QVBoxLayout, "digitalTwinsTabLayout")
        self._search_bar = self.tab_widget.findChild(QtWidgets.QLineEdit, "digitalTwinsSearchLineEdit")
        self._clear_filters_button = self.tab_widget.findChild(
            QtWidgets.QPushButton, "digitalTwinsClearFiltersButton"
        )
        self._cards_container = self.tab_widget.findChild(
            QtWidgets.QWidget, "digitalTwinsScrollAreaContents"
        )

        self._filter_lists = {
            "owner_hubs": self.tab_widget.findChild(
                QtWidgets.QListWidget, "digitalTwinsOwnerHubFiltersList"
            ),
            "findability": self.tab_widget.findChild(
                QtWidgets.QListWidget, "digitalTwinsFindabilityFiltersList"
            ),
        }
        self._filter_toggles = {
            "owner_hubs": self.tab_widget.findChild(
                QtWidgets.QToolButton, "digitalTwinsOwnerHubFiltersToggleButton"
            ),
            "findability": self.tab_widget.findChild(
                QtWidgets.QToolButton, "digitalTwinsFindabilityFiltersToggleButton"
            ),
        }

        for key, widget in self._filter_lists.items():
            self._init_filter_list(
                widget,
                lambda _item, filter_key=key: self._on_filter_changed(filter_key),
            )
            self._init_collapsible_filter(self._filter_toggles.get(key), widget)

        if self._clear_filters_button is not None:
            self._clear_filters_button.setText(self.CLEAR_FILTERS_TEXT)
            self._clear_filters_button.clicked.connect(self._clear_all_filters)

        self._setup_pagination_ui()

        if self._search_bar is not None:
            self._search_bar.setClearButtonEnabled(True)
            self._search_bar.textChanged.connect(self._on_search_text_changed)

        self.render_digital_twins([])

    def _init_filter_list(self, widget, changed_handler):
        if widget is None:
            return
        widget.setSelectionMode(NO_SELECTION_MODE)
        widget.itemChanged.connect(changed_handler)

    def _init_collapsible_filter(self, toggle_button, body_widget):
        if toggle_button is None or body_widget is None:
            return
        toggle_button.setCheckable(True)
        expanded = toggle_button.isChecked()
        body_widget.setVisible(expanded)
        toggle_button.setArrowType(ARROW_DOWN if expanded else ARROW_RIGHT)
        toggle_button.toggled.connect(
            lambda checked, button=toggle_button, body=body_widget: self._set_filter_section_expanded(
                button, body, checked
            )
        )

    def _set_filter_section_expanded(self, toggle_button, body_widget, expanded):
        body_widget.setVisible(expanded)
        toggle_button.setArrowType(ARROW_DOWN if expanded else ARROW_RIGHT)

    def _setup_pagination_ui(self):
        if self._main_layout is None:
            return

        pagination_widget = QWidget(self.tab_widget)
        pagination_layout = QHBoxLayout(pagination_widget)
        pagination_layout.setContentsMargins(0, 8, 0, 8)

        self.prev_button = QtWidgets.QPushButton("Previous", pagination_widget)
        self.next_button = QtWidgets.QPushButton("Next", pagination_widget)
        self.page_label = QLabel("Page 1 of 1", pagination_widget)

        pagination_layout.addStretch()
        pagination_layout.addWidget(self.prev_button)
        pagination_layout.addWidget(self.page_label)
        pagination_layout.addWidget(self.next_button)
        pagination_layout.addStretch()

        self._main_layout.addWidget(pagination_widget)

        self.prev_button.clicked.connect(self._on_prev_page)
        self.next_button.clicked.connect(self._on_next_page)
        self._update_pagination_ui()

    def _update_pagination_ui(self):
        if self.page_label is None or self.prev_button is None or self.next_button is None:
            return
        total_pages = max(1, (self.total_count + self.page_size - 1) // self.page_size)
        max_page = total_pages - 1
        if self.current_page > max_page:
            self.current_page = max_page
        self.page_label.setText(f"Page {self.current_page + 1} of {total_pages}")
        self.prev_button.setEnabled(self.current_page > 0)
        self.next_button.setEnabled(self.current_page < max_page)

    def _on_prev_page(self):
        if self.current_page <= 0:
            return
        self.current_page -= 1
        self._refresh_filtered_view()

    def _on_next_page(self):
        max_page = max(0, (self.total_count + self.page_size - 1) // self.page_size - 1)
        if self.current_page >= max_page:
            return
        self.current_page += 1
        self._refresh_filtered_view()

    def _active_search_query(self):
        return self._search_bar.text() if self._search_bar is not None else ""

    def _on_search_text_changed(self, _text):
        self.current_page = 0
        self._refresh_filtered_view()

    def _on_filter_changed(self, filter_key):
        self._selected_filters[filter_key] = self._checked_values(self._filter_lists.get(filter_key))
        self.current_page = 0
        self._refresh_filtered_view()

    def _clear_all_filters(self):
        for list_widget in self._filter_lists.values():
            self._uncheck_all_items(list_widget)
        for key in self._selected_filters:
            self._selected_filters[key] = set()
        self.current_page = 0
        self._refresh_filtered_view()

    def _uncheck_all_items(self, list_widget):
        if list_widget is None:
            return
        list_widget.blockSignals(True)
        for index in range(list_widget.count()):
            list_widget.item(index).setCheckState(UNCHECKED_STATE)
        list_widget.blockSignals(False)

    def _checked_values(self, list_widget):
        if list_widget is None:
            return set()
        selected = set()
        for index in range(list_widget.count()):
            item = list_widget.item(index)
            if item.checkState() == CHECKED_STATE:
                selected.add(item.data(USER_ROLE))
        return selected

    def _normalize_text(self, value):
        return str(value or "").strip()

    def _normalize_key(self, value):
        return self._normalize_text(value).lower()

    def _dedupe_values(self, values):
        seen = set()
        result = []
        for value in values or []:
            text = self._normalize_text(value)
            if not text:
                continue
            key = self._normalize_key(text)
            if key in seen:
                continue
            seen.add(key)
            result.append(text)
        return result

    def _twin_owner_hubs(self, twin):
        owner_hub = self._normalize_text(twin.get("owner_hub") or twin.get("title"))
        return [owner_hub] if owner_hub else []

    def _twin_part_of_hubs(self, twin):
        values = twin.get("part_of_hubs")
        if isinstance(values, (list, tuple, set)):
            return self._dedupe_values(values)

        single_value = self._normalize_text(twin.get("part_of_hub"))
        if not single_value:
            return []
        return self._dedupe_values([part.strip() for part in single_value.split(",")])

    def _twin_findability_values(self, twin):
        values = twin.get("findability_values")
        if isinstance(values, (list, tuple, set)):
            return [self._normalize_text(value).upper() for value in values if self._normalize_text(value)]

        raw = self._normalize_text(twin.get("findability"))
        if not raw:
            return ["UNKNOWN"]
        return [self._normalize_text(value).upper() for value in raw.split(",") if self._normalize_text(value)]

    def _findability_label(self, value):
        raw_value = self._normalize_text(value)
        if not raw_value:
            return "Unknown"

        labels = {
            "PUBLIC": "Public (discoverable by everyone)",
            "PRIVATE": "Private (restricted to owner access)",
            "RESTRICTED": "Restricted (limited visibility)",
            "INTERNAL": "Internal (organization only)",
        }
        upper_value = raw_value.upper()
        return labels.get(upper_value, raw_value.replace("_", " ").title())

    def _refresh_list_widget(self, list_widget, available, filter_key):
        if list_widget is None:
            return

        preserved = {
            value for value in self._selected_filters[filter_key] if value in available
        }

        list_widget.blockSignals(True)
        list_widget.clear()
        for normalized, display in sorted(available.items(), key=lambda item: item[1].lower()):
            item = QtWidgets.QListWidgetItem(display)
            item.setData(USER_ROLE, normalized)
            item.setFlags(item.flags() | ITEM_IS_USER_CHECKABLE)
            item.setCheckState(CHECKED_STATE if normalized in preserved else UNCHECKED_STATE)
            list_widget.addItem(item)
        list_widget.blockSignals(False)

        self._selected_filters[filter_key] = preserved

    def _refresh_owner_hubs_sidebar(self):
        available = {}
        for twin in self._all_digital_twins:
            for owner_hub in self._twin_owner_hubs(twin):
                available[self._normalize_key(owner_hub)] = owner_hub
        self._refresh_list_widget(self._filter_lists.get("owner_hubs"), available, "owner_hubs")

    def _refresh_findability_sidebar(self):
        available = {}
        for twin in self._all_digital_twins:
            for value in self._twin_findability_values(twin):
                available[value] = self._findability_label(value)
        self._refresh_list_widget(self._filter_lists.get("findability"), available, "findability")

    def _matches_search(self, twin, query):
        needle = self._normalize_text(query).lower()
        if not needle:
            return True
        haystack = " ".join(
            [
                self._normalize_text(twin.get("title")),
                self._normalize_text(twin.get("description")),
                " ".join(self._twin_owner_hubs(twin)),
                " ".join(self._twin_part_of_hubs(twin)),
                " ".join(self._twin_findability_values(twin)),
                self._normalize_text(twin.get("formats")),
                self._normalize_text(twin.get("datasets_count")),
            ]
        ).lower()
        return needle in haystack

    def _matches_any_selected(self, values, filter_key):
        selected = self._selected_filters[filter_key]
        if not selected:
            return True
        normalized_values = {self._normalize_key(value) for value in values if self._normalize_text(value)}
        return bool(normalized_values & selected)

    def _matches_findability_filter(self, twin):
        selected = self._selected_filters["findability"]
        if not selected:
            return True
        return bool(set(self._twin_findability_values(twin)) & selected)

    def _matches_filters(self, twin):
        return (
            self._matches_any_selected(self._twin_owner_hubs(twin), "owner_hubs")
            and self._matches_findability_filter(twin)
        )

    def _refresh_filtered_view(self):
        self._render_filtered_digital_twins(self._active_search_query())

    def _render_filtered_digital_twins(self, query=""):
        filtered = [
            twin
            for twin in self._all_digital_twins
            if self._matches_search(twin, query) and self._matches_filters(twin)
        ]
        self.total_count = len(filtered)
        max_page = max(0, (self.total_count + self.page_size - 1) // self.page_size - 1)
        if self.current_page > max_page:
            self.current_page = max_page

        start = self.current_page * self.page_size
        end = start + self.page_size
        self._render_digital_twin_cards(filtered[start:end])
        self._update_pagination_ui()

    def render_digital_twins(self, digital_twins):
        self._all_digital_twins = digital_twins or []
        self.current_page = 0
        self._refresh_owner_hubs_sidebar()
        self._refresh_findability_sidebar()
        self._refresh_filtered_view()

    def _ensure_cards_layout(self):
        if not self._cards_container:
            return None
        layout = self._cards_container.layout()
        if layout is None:
            layout = QVBoxLayout()
            self._cards_container.setLayout(layout)
        return layout

    def _clear_layout_widgets(self, layout):
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def _create_digital_twin_card(self, twin):
        owner_hub = ", ".join(self._twin_owner_hubs(twin)) or "No Hub"
        part_of_hub = ", ".join(self._twin_part_of_hubs(twin)) or "—"
        findability_values = self._twin_findability_values(twin)
        findability = ", ".join(self._findability_label(value) for value in findability_values) or "Unknown"
        profile_picture_url = self._normalize_text(twin.get("profile_picture_url"))

        frame = QFrame()
        frame.setObjectName("digitalTwinCard")

        frame_layout = QHBoxLayout(frame)
        frame_layout.setContentsMargins(12, 10, 12, 10)
        frame_layout.setSpacing(12)

        preview = self._create_preview_label(profile_picture_url)

        title = QLabel(twin.get("title", "No Title"))
        description = QLabel(twin.get("description", "No Description"))
        description.setWordWrap(True)
        owner_hub_label = QLabel(f"Owner hub: {owner_hub}")
        part_of_hub_label = QLabel(f"Part of hub: {part_of_hub}")
        findability_label = QLabel(f"Findability: {findability}")
        datasets_count = QLabel(f"Datasets: {twin.get('datasets_count', 0)}")
        formats = QLabel(f"Formats: {twin.get('formats', 'Unknown')}")

        load_button = QtWidgets.QPushButton(self.LOAD_BUTTON_TEXT)
        load_button.setMaximumWidth(500)
        load_button.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        twin_id = twin.get("id")
        load_button.clicked.connect(
            lambda checked, dt_id=twin_id: self.digital_twin_load_requested.emit(dt_id)
        )

        info_layout = QVBoxLayout()
        info_layout.setSpacing(6)
        info_layout.addWidget(title)
        info_layout.addWidget(description)
        info_layout.addWidget(owner_hub_label)
        info_layout.addWidget(part_of_hub_label)
        info_layout.addWidget(findability_label)
        info_layout.addWidget(datasets_count)
        info_layout.addWidget(formats)
        info_layout.addWidget(load_button)

        frame_layout.addWidget(preview)
        frame_layout.addLayout(info_layout, 1)
        return frame

    def _create_preview_label(self, profile_picture_url):
        preview = QLabel("No preview")
        preview.setFixedSize(280, 158)
        preview.setAlignment(ALIGN_CENTER)
        preview.setWordWrap(True)

        if not profile_picture_url:
            return preview

        request = QNetworkRequest(QUrl(profile_picture_url))
        reply = self._network_manager.get(request)
        self._image_requests[reply] = preview
        preview.setText("Loading preview...")
        return preview

    def _on_preview_image_loaded(self, reply):
        preview = self._image_requests.pop(reply, None)
        if preview is None:
            reply.deleteLater()
            return

        error_code = getattr(reply, "error", lambda: None)()
        no_error = getattr(reply, "NetworkError", None)
        no_error_value = getattr(no_error, "NoError", 0) if no_error is not None else 0
        if error_code != no_error_value:
            try:
                preview.setText("Preview unavailable")
            except RuntimeError:
                pass
            reply.deleteLater()
            return

        data = bytes(reply.readAll())
        pixmap = QPixmap()
        if not data or not pixmap.loadFromData(data):
            try:
                preview.setText("Preview unavailable")
            except RuntimeError:
                pass
            reply.deleteLater()
            return

        try:
            preview.setPixmap(
                pixmap.scaled(
                    preview.width(),
                    preview.height(),
                    getattr(Qt, "AspectRatioMode", Qt).KeepAspectRatio,
                    getattr(Qt, "TransformationMode", Qt).SmoothTransformation,
                )
            )
        except RuntimeError:
            pass
        reply.deleteLater()

    def _render_digital_twin_cards(self, digital_twins):
        layout = self._ensure_cards_layout()
        if layout is None:
            return
        self._clear_layout_widgets(layout)
        for twin in digital_twins:
            layout.addWidget(self._create_digital_twin_card(twin))
        layout.addStretch()
