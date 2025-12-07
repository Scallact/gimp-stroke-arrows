# Stroke Arrows - GIMP 3.xx python plug-in

Stroke one or several paths as arrows. The body/shaft path is shortened to ensure that the arrow tip ends up reasonably well aligned with the path's last point.

A few styles are available for the arrowhead and tail, and the body/shaft is a standard line stroke with configurable width.

## Usage:

* Draw a path with at least two points. Any complex path should work.
* Select the path in the paths dialog.
* Launch the plug-in with **Edit > Stroke arrows...** or **right-click in the paths dialog > Stroke arrows...**
* The path and arrowhead are drawn with the foreground color. You can still change the FG color while the plug-in dialog is open.

<img width="400" height="200" alt="StrokeArrow02" src="https://github.com/user-attachments/assets/d982fed7-55fb-4079-bee7-c2c5440bf5b5" />

Some of the plugin possibilities:

<img width="470" height="340" alt="StrokeArrow04-samples01s" src="https://github.com/user-attachments/assets/8feeb8b1-e1f5-4063-8a4a-9297ee34fa78" />

## Installation:

Unzip and copy the folder named "pl_stroke_arrows" into GIMP's "plug-ins" folder inside your user profile. Make sure the file "pl_stroke_arrows.py" is inside, and set that file executable on Linux and MacOS. Usually with a right click to access files properties on Linux.

(Re)start GIMP, the plug-in should be visible at the bottom of the "Edit" menu.

## Parameters:

* **Color**: Simple color choice between black and foreground color. The foreground color can be chosen while the dialog is opened.
* **Arrowhead style**: see illustration below
    * filled
    * empty
    * simple
* **Wing length (px)**: Length of arrowhead wings in pixels. The actual wing size can vary slightly if the "Shape" parameter is negative.
* **Tip angle (°)**: makes the arrowhead more or less pointy.
* **Shape**: determines the shape at the back of the arrowhead. A positive offset creates a harpoon shaped arrowhead. An offset of 0 creates a flat end. A negative offset creates a diamond shaped arrowhead.
* **Stroke width (px)**: Width of the shaft and outlines strokes.
* **Tail type**: see image below
   * none
   * bar
   * bullet
   * feather
   * two-way arrow
* **Tail style**: not applicable for "none" and "bar" types
   * same as arrowhead
   * filled
   * empty
   * simple
* **Tail width**
* **Tail width unit relative (%)** : relative to the arrow width in % if checked, absolute value in pixels if unchecked.
* **Create new layer**: unchecked - draw on the selected layer / checked: create a new layer with appropriate size
* **Flip direction**: reverse the direction of the selected paths.
* **Remove shaft, draw head**: check to draw head only or head and tail only.
* **Remove shaft, draw tail**: check to draw tail only or head and tail only.
* **Keep newly created paths**: keep the paths used to draw the arrows.

### Shape parameter:

<img width="402" height="552" alt="StrokeArrow01_1" src="https://github.com/user-attachments/assets/34203033-f8a6-4048-9243-a2b274ea14d8" />

### All possible pairings of arrowhead styles and tail types/styles:

<img width="1322" height="752" alt="StrokeArrow03_inventory03" src="https://github.com/user-attachments/assets/16d86062-a8bc-4d02-ad8c-84648e8d2a4d" />

