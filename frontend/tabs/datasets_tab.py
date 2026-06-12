"""Datasets tab controller bound to widgets designed in main_window.ui."""

from qgis.PyQt import QtWidgets
from qgis.PyQt.QtCore import QObject, Qt, pyqtSignal
from qgis.PyQt.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

# PyQt enum compatibility (QGIS 4 / PyQt6, with PyQt5 fallback names).
NO_SELECTION_MODE = getattr(
    QtWidgets.QAbstractItemView, "SelectionMode", QtWidgets.QAbstractItemView
).NoSelection
CHECKED_STATE = getattr(Qt, "CheckState", Qt).Checked
UNCHECKED_STATE = getattr(Qt, "CheckState", Qt).Unchecked
USER_ROLE = getattr(Qt, "ItemDataRole", Qt).UserRole
ITEM_IS_USER_CHECKABLE = getattr(Qt, "ItemFlag", Qt).ItemIsUserCheckable
INSTANT_POPUP = getattr(
    QtWidgets.QToolButton, "ToolButtonPopupMode", QtWidgets.QToolButton
).InstantPopup
ARROW_RIGHT = getattr(Qt, "ArrowType", Qt).RightArrow
ARROW_DOWN = getattr(Qt, "ArrowType", Qt).DownArrow


class DatasetsTab(QObject):
    page_changed = pyqtSignal(int, int)
    dataset_load_requested = pyqtSignal(str, str, str, str)

    CLEAR_FILTERS_TEXT = "Clear filters"
    LOAD_BUTTON_TEXT = "Resources"

    def __init__(self, tab_widget):
        super().__init__(tab_widget)
        self.tab_widget = tab_widget
        self._is_authenticated = False

        self.current_page = 0
        self.page_size = 20
        self.total_count = 0
        self.prev_button = None
        self.next_button = None
        self.page_label = None

        self._all_datasets = []
        self._selected_filters = {
            "owner_hubs": set(),
            "tags": set(),
            "findability": set(),
            "formats": set(),
        }

        self._main_layout = self.tab_widget.findChild(QtWidgets.QVBoxLayout, "datasetsTabLayout")
        self._search_bar = self.tab_widget.findChild(QtWidgets.QLineEdit, "datasetsSearchLineEdit")
        self._clear_filters_button = self.tab_widget.findChild(
            QtWidgets.QPushButton, "datasetsClearFiltersButton"
        )
        self._cards_container = self.tab_widget.findChild(QtWidgets.QWidget, "datasetsScrollAreaContents")

        self._filter_lists = {
            "owner_hubs": self.tab_widget.findChild(
                QtWidgets.QListWidget, "datasetsOwnerHubFiltersList"
            ),
            "tags": self.tab_widget.findChild(QtWidgets.QListWidget, "datasetsTagsFiltersList"),
            "findability": self.tab_widget.findChild(
                QtWidgets.QListWidget, "datasetsFindabilityFiltersList"
            ),
            "formats": self.tab_widget.findChild(
                QtWidgets.QListWidget, "datasetsFormatFiltersList"
            ),
        }
        self._filter_toggles = {
            "owner_hubs": self.tab_widget.findChild(
                QtWidgets.QToolButton, "datasetsOwnerHubFiltersToggleButton"
            ),
            "tags": self.tab_widget.findChild(
                QtWidgets.QToolButton, "datasetsTagsFiltersToggleButton"
            ),
            "findability": self.tab_widget.findChild(
                QtWidgets.QToolButton, "datasetsFindabilityFiltersToggleButton"
            ),
            "formats": self.tab_widget.findChild(
                QtWidgets.QToolButton, "datasetsFormatFiltersToggleButton"
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

        self._update_findability_visibility()
        self.render_datasets([], total_count=0)

    def set_authenticated(self, is_authenticated):
        self._is_authenticated = bool(is_authenticated)
        self._update_findability_visibility()
        self.current_page = 0
        self._refresh_filtered_view()

    def _update_findability_visibility(self):
        findability_list = self._filter_lists.get("findability")
        findability_toggle = self._filter_toggles.get("findability")
        visible = self._is_authenticated

        if findability_toggle is not None:
            findability_toggle.setVisible(visible)
        if findability_list is not None:
            findability_list.setVisible(visible)

        if not visible:
            self._selected_filters["findability"] = set()
            self._uncheck_all_items(findability_list)

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

    def set_total_count(self, count):
        self.total_count = max(0, int(count or 0))
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

    def set_page(self, page):
        self.current_page = max(0, int(page or 0))
        self._update_pagination_ui()

    def set_page_size(self, size):
        self.page_size = max(1, int(size or 20))
        self.current_page = 0
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

    def _multi_value_field(self, dataset, list_key, single_key=None):
        values = dataset.get(list_key)
        if isinstance(values, (list, tuple, set)):
            return self._dedupe_values(values)

        if single_key:
            single_value = self._normalize_text(dataset.get(single_key))
            return [single_value] if single_value else []
        return []

    def _dataset_owner_hubs(self, dataset):
        owner_hub = self._normalize_text(dataset.get("owner_hub") or dataset.get("hub"))
        return [owner_hub] if owner_hub else []

    def _dataset_tags(self, dataset):
        return self._multi_value_field(dataset, "tags")

    def _dataset_findability_value(self, dataset):
        value = self._normalize_text(dataset.get("findability")).upper()
        return value or "UNKNOWN"

    def _dataset_formats(self, dataset):
        formats = self._multi_value_field(dataset, "formats")
        if formats:
            return [self._normalize_text(fmt).lower() for fmt in formats if self._normalize_text(fmt)]

        collected = []
        primary_format = self._normalize_text(dataset.get("format"))
        if primary_format and primary_format.lower() != "unknown format":
            collected.append(primary_format.lower())

        for resource in dataset.get("resources") or []:
            resource_format = self._normalize_text(resource.get("format"))
            if resource_format and resource_format.lower() != "unknown format":
                collected.append(resource_format.lower())

        return self._dedupe_values(collected)

    def _findability_label(self, dataset):
        return self._findability_label_from_value(self._dataset_findability_value(dataset))

    def _findability_label_from_value(self, value):
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

    def _format_display(self, fmt):
        normalized = self._normalize_text(fmt)
        return normalized.upper() if normalized else "Unknown"

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
        for dataset in self._all_datasets:
            for owner_hub in self._dataset_owner_hubs(dataset):
                available[self._normalize_key(owner_hub)] = owner_hub
        self._refresh_list_widget(self._filter_lists.get("owner_hubs"), available, "owner_hubs")

    def _refresh_tags_sidebar(self):
        available = {}
        for dataset in self._all_datasets:
            for tag in self._dataset_tags(dataset):
                available[self._normalize_key(tag)] = tag
        self._refresh_list_widget(self._filter_lists.get("tags"), available, "tags")

    def _refresh_findability_sidebar(self):
        available = {}
        for dataset in self._all_datasets:
            normalized = self._dataset_findability_value(dataset)
            available[normalized] = self._findability_label_from_value(normalized)
        self._refresh_list_widget(self._filter_lists.get("findability"), available, "findability")

    def _refresh_formats_sidebar(self):
        available = {}
        for dataset in self._all_datasets:
            for fmt in self._dataset_formats(dataset):
                available[self._normalize_key(fmt)] = self._format_display(fmt)
        self._refresh_list_widget(self._filter_lists.get("formats"), available, "formats")

    def _matches_search(self, dataset, query):
        needle = self._normalize_text(query).lower()
        if not needle:
            return True

        haystack = " ".join(
            [
                self._normalize_text(dataset.get("title")),
                self._normalize_text(dataset.get("description")),
                " ".join(self._dataset_owner_hubs(dataset)),
                " ".join(self._dataset_tags(dataset)),
                " ".join(self._dataset_formats(dataset)),
                self._findability_label(dataset),
            ]
        ).lower()
        return needle in haystack

    def _matches_any_selected(self, values, filter_key):
        selected = self._selected_filters[filter_key]
        if not selected:
            return True
        normalized_values = {self._normalize_key(value) for value in values if self._normalize_text(value)}
        return bool(normalized_values & selected)

    def _matches_findability_filter(self, dataset):
        if not self._is_authenticated:
            return True
        selected = self._selected_filters["findability"]
        if not selected:
            return True
        return self._dataset_findability_value(dataset) in selected

    def _matches_filters(self, dataset):
        return (
            self._matches_any_selected(self._dataset_owner_hubs(dataset), "owner_hubs")
            and self._matches_any_selected(self._dataset_tags(dataset), "tags")
            and self._matches_findability_filter(dataset)
            and self._matches_any_selected(self._dataset_formats(dataset), "formats")
        )

    def _refresh_filtered_view(self):
        self._render_filtered_datasets(self._active_search_query())

    def _render_filtered_datasets(self, query=""):
        filtered_datasets = [
            dataset
            for dataset in self._all_datasets
            if self._matches_search(dataset, query) and self._matches_filters(dataset)
        ]

        self.total_count = len(filtered_datasets)
        max_page = max(0, (self.total_count + self.page_size - 1) // self.page_size - 1)
        if self.current_page > max_page:
            self.current_page = max_page

        start = self.current_page * self.page_size
        end = start + self.page_size
        self._render_dataset_cards(filtered_datasets[start:end])
        self._update_pagination_ui()

    def render_datasets(self, datasets, total_count=None):
        _ = total_count
        self._all_datasets = datasets or []
        self.current_page = 0
        self._refresh_owner_hubs_sidebar()
        self._refresh_tags_sidebar()
        self._refresh_findability_sidebar()
        self._refresh_formats_sidebar()
        self._refresh_filtered_view()

    def _ensure_dataset_cards_layout(self):
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

    def _create_dataset_card(self, dataset):
        owner_hub = ", ".join(self._dataset_owner_hubs(dataset)) or "No Hub"
        tags = ", ".join(self._dataset_tags(dataset)) or "—"
        formats = ", ".join(self._format_display(fmt) for fmt in self._dataset_formats(dataset)) or "Unknown"

        frame = QFrame()
        frame.setObjectName("datasetCard")

        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(12, 10, 12, 10)
        frame_layout.setSpacing(8)

        title = QLabel(dataset.get("title", "No Title"))
        description = QLabel(dataset.get("description", "No Description"))
        owner_hub_label = QLabel(f"Owner hub: {owner_hub}")
        tags_label = QLabel(f"Tags: {tags}")
        formats_label = QLabel(f"Formats: {formats}")
        description.setWordWrap(True)
        tags_label.setWordWrap(True)

        dataset_id = dataset.get("id")
        valid_resources = [resource for resource in (dataset.get("resources") or []) if resource.get("url")]

        load_button = QtWidgets.QToolButton()
        load_button.setText(self.LOAD_BUTTON_TEXT)
        load_button.setPopupMode(INSTANT_POPUP)
        load_button.setMaximumWidth(500)
        load_button.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )

        menu = QtWidgets.QMenu(load_button)

        if len(valid_resources) > 1:
            load_all_action = menu.addAction("Load All Resources")
            load_all_action.triggered.connect(
                lambda checked, did=dataset_id, resources=valid_resources: self._load_all_resources(did, resources)
            )
            menu.addSeparator()

        for resource in valid_resources:
            resource_name = resource.get("name") or "Unnamed Resource"
            resource_url = resource.get("url", "")
            resource_format = resource.get("format", "")
            fmt_display = resource_format.upper() if resource_format else "Unknown"
            action = menu.addAction(f"{resource_name}  ({fmt_display})")
            action.triggered.connect(
                lambda checked, did=dataset_id, url=resource_url, fmt=resource_format, name=resource_name: self.dataset_load_requested.emit(
                    did, url, fmt, name
                )
            )
        load_button.setMenu(menu)
        load_button.setEnabled(bool(valid_resources))

        frame_layout.addWidget(title)
        frame_layout.addWidget(description)
        frame_layout.addWidget(owner_hub_label)
        frame_layout.addWidget(tags_label)
        frame_layout.addWidget(formats_label)
        if self._is_authenticated:
            findability = QLabel(f"Findability: {self._findability_label(dataset)}")
            frame_layout.addWidget(findability)
        frame_layout.addWidget(load_button)
        return frame

    def _load_all_resources(self, dataset_id, resources):
        for resource in resources:
            self.dataset_load_requested.emit(
                dataset_id,
                resource.get("url", ""),
                resource.get("format", ""),
                resource.get("name") or "Unnamed Resource",
            )

    def _render_dataset_cards(self, datasets):
        layout = self._ensure_dataset_cards_layout()
        if layout is None:
            return

        self._clear_layout_widgets(layout)
        for dataset in datasets:
            layout.addWidget(self._create_dataset_card(dataset))
        layout.addStretch()
