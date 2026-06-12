# from qgis.PyQt import QtWidgets
# from qgis.PyQt.QtCore import QObject
# from qgis.PyQt.QtWidgets import QFrame, QLabel, QVBoxLayout
#
#
# class HubsTab(QObject):
#     def __init__(self, tab_widget):
#         super().__init__(tab_widget)
#         self.tab_widget = tab_widget
#         self._all_hubs = []
#         self._cards_container = self.tab_widget.findChild(
#             QtWidgets.QWidget, "hubsScrollAreaContents"
#         )
#
#     def render_hubs(self, hubs):
#         self._all_hubs = hubs or []
#         self._render_filtered_hubs()
#
#     def _ensure_cards_layout(self):
#         if not self._cards_container:
#             return None
#
#         layout = self._cards_container.layout()
#         if layout is None:
#             layout = QVBoxLayout()
#             self._cards_container.setLayout(layout)
#         return layout
#
#     def _clear_layout_widgets(self, layout):
#         while layout.count():
#             child = layout.takeAt(0)
#             if child.widget():
#                 child.widget().deleteLater()
#
#     def _create_hub_card(self, hub):
#         frame = QFrame()
#         frame_layout = QVBoxLayout(frame)
#
#         title = QLabel(hub.get("name") or "Unnamed Hub")
#         description = QLabel(hub.get("description") or "No Description")
#         description.setWordWrap(True)
#
#         frame_layout.addWidget(title)
#         frame_layout.addWidget(description)
#         return frame
#
#     def _render_filtered_hubs(self):
#         layout = self._ensure_cards_layout()
#         if layout is None:
#             return
#
#         self._clear_layout_widgets(layout)
#
#         for hub in self._all_hubs:
#             layout.addWidget(self._create_hub_card(hub))
#
#         layout.addStretch()
