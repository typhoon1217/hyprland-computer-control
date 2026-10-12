import QtQuick
import Quickshell
import Quickshell.Hyprland
ShellRoot {
  property int ipcMonitorCount: Hyprland.monitors.values.length
  onIpcMonitorCountChanged: console.log("IPC_MONITORS=" + ipcMonitorCount)
  FloatingWindow {
    id: window
    onWidthChanged: ready.restart()
    onHeightChanged: ready.restart()
    Timer { id: ready; interval: 150; onTriggered: console.log("READY=" + window.width + "x" + window.height) }
    visible: true
    screen: Quickshell.screens.find(s => s.name === "HEADLESS-1")
    implicitWidth: 640
    implicitHeight: 480
    color: "#181b22"
    Text {
      anchors.horizontalCenter: parent.horizontalCenter
      y: 40
      text: "hypr-ccv isolated input smoke"
      color: "white"
      font.pixelSize: 24
    }
    Rectangle {
      anchors.centerIn: parent
      anchors.verticalCenterOffset: -80
      width: Math.min(500, parent.width - 40)
      height: 50
      color: "white"
      TextInput {
        anchors.fill: parent
        anchors.margins: 10
        font.pixelSize: 20
        onAccepted: console.log("INPUT=" + text)
      }
    }
    Rectangle {
      anchors.centerIn: parent
      anchors.verticalCenterOffset: 10
      width: 180
      height: 50
      color: "#3775a9"
      property int clicks: 0
      Text { anchors.centerIn: parent; text: "Clicks: " + parent.clicks; color: "white"; font.pixelSize: 20 }
      MouseArea { anchors.fill: parent; onClicked: { parent.clicks++; console.log("CLICK=" + parent.clicks) } }
    }
  }
}
