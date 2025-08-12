# Stroke Arrows - GIMP python plug-in

This plug-in has a simple purpose: to stroke one or several paths with an arrowhead inserted at the end. The body path is shortened to ensure that the arrow tip ends up reasonably well aligned with the path's last point.

A few styles are available for the arrowhead, and the body is a standard line stroke with configurable width.

Usage:

* Draw a path with at least two points. Any complex path should work.
* Select the path in the paths dialog.
* Launch the plug-in with Edit > Stroke arrows...
* The path and arrowhead are drawn with the foreground color. You can still change the FG color while the plug-in dialog is open.

<img width="400" height="200" alt="StrokeArrow02" src="https://github.com/user-attachments/assets/d982fed7-55fb-4079-bee7-c2c5440bf5b5" />

## Parameters:

* Arrowhead style: see illustration below
    * filled
    * empty
    * simple
* Stroke width (px): self explanatory. For "empty" style arrowheads, the outline has always the same width as the body.
* Arrowhead length (px): measured from the tip to the exterior point of the wings, projected alongside the axe. Apparent size can vary slightly depending on the chosen style
* Tip angle (°): makes the arrowhead more or less pointy.
* Anchor offset: determines the shape at the back of the arrowhead. A positive offset creates a harpoon shaped arrowhead. An offset of 0 creates a flat end. A negative offset creates a diamond shaped arrowhead.
* Draw arrowheads only: if checked, the body is not drawn
* Create new layer: unchecked - draw on the selected layer / checked: create a new layer with appropriate size.
* Keep paths: keep the shortened body path and the arrowhead path, for the cases where more customisation is wanted.

<img width="402" height="552" alt="StrokeArrow01" src="https://github.com/user-attachments/assets/ea2f35bc-48c7-4c39-86ec-363260e87ad7" />

## Installation:

Unzip and copy the folder named "pl_stroke_arrows" into GIMP's "plug-ins" folder inside your user profile. Make sure the file "pl_stroke_arrows.py" is inside, and make that file executable, usually with a right click to access files properties (at least on Linux, I don't know how other OS's seal with python executables).

(Re)start GIMP, the plug-in should be visible at the bottom of the "Edit" menu.
