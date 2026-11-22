import QtQuick
import Quickshell
import qs.Commons
import qs.Ui

BarWidget {
  id: root
  moduleName: "omarchy.sysmon"

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: "\uf201"
    slotSize: Style.bar.statusSlot
    tooltipText: "Omarchy System Monitor"
    onPressed: {
      if (root.bar) root.bar.run("omarchy-sysmon-toggle")
    }
  }
}
