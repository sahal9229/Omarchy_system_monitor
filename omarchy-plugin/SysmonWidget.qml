import QtQuick
import Quickshell
import qs.Commons
import qs.Ui

BarWidget {
  id: root
  moduleName: "sahal.sysmon"

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: "󰈐"
    slotSize: Style.bar.statusSlot
    tooltipText: "Omarchy System Monitor"
    onPressed: function(b) {
      if (root.bar) root.bar.run("omarchy-sysmon-toggle")
    }
  }
}
