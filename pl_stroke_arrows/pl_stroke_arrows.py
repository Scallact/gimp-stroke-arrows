#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Description du script
#
# Original author : Pascal L.
# Version 0.7 for GIMP 3.0

# ------------------

# License: GPLv3
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY, without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# To view a copy of the GNU General Public License
# visit: http://www.gnu.org/licenses/gpl.html

# ------------------

# Changelog
# ---------
# 0.1 :
# - initial planned fonctionality complete
#
# 0.2 :
# - dealt with case when second last anchor is too close to the end.
# - changed (user) scale and renamed harpoon factor to "anchor point position".
# - extended stroke for better contact between head and body.
# - corrected an issue with incorrect direction calculation in edge cases, by using 
#    dot product (obsolete).
# - checked case where path is too short - clean error report still to figure out.
# - shrink and displace arrow head for empty and simple.
# - option to create new layer.
# - prepared for exact calculation of anchor point and tangents, not yet plugged in.
# - take existing selection correctly into account.
# - limited positive harpoon factor to 6.
#
# 0.3 :
# - plugged in exact calculation of anchor point and tangents (Bezier).
# - adapted anchor angle calculation.
# - target segment detection more robust, as some edge cases failed to find the target.
#
# 0.4 :
# - refactored the anchor Bezier search to include an arbitrary number of segment. 
#    In case of failure, the search starts again with more segments.
# - better error management (no path, break from loops...).
# - defined pointy corner limit for empty and simple.
# - reselected current layer at the end.
#
# 0.5 :
# - added the patch at the end of the body (not just as another joint stroke).
# - cleaned code.
# - context for stroke (not global: let user change FG).
# - general changes from coord lists to points lists.
# - implemented standard Bezier search algorithm with 5 points and distances.
#   - above fixes bug with bug_strokeArrows_04.xcf
#   - added bigger increment at each try for number of segments, fixes bug_strokeArrows_05.xcf
# - many bug fixes after the algorithm and points lists refactoring.
# - changed menu location from "Tools" to "Edit".
#
# 0.6 :
# - revrote code for cutting the spline. Now takes the full spline into account, does 
#    a simple iterative sum of tiny distances, replacing the API call which does not 
#   provide the t parameter and required an additional iterative search.
# - the above corrected a bug when 3 or more segments where inside the arrowhead
# - initial restructuring of the code.
# - enhanced junction of arrowhead and body placement by decoupling anchor point and  
#    spline cut point when (internal) harpoon factor is small.
# - revrote case of splines too small to place the arrowhead and cut point.
# - corrected error when layer mask or channel is selected.
#
#  0.7 :
# - restructured most the code to enable arrow tails
# - added 5 types of arrow tails:
#       none
#       bar
#       bullet
#       feather
#       two-way arrowhead
# - 3 styles of arrow tails that match the head styles
# - better error handling
# - take the pointy wings into account when resizing empty harpoon arrowhead
# - take the back point into account when resizing empty diamond arrowhead
# - diamond arrowhead user chosen size is taken from a ratio of the back part for better 
#    optical sizing
# - resize the empty and simple arrow tails (feathered and bullet)
# - added relative unit for tail (relative to the head width)
# - added reverse path option
# - completed the options to remove the shaft, while keeping the head or tail or both
# - user dialog with better labels
# - user dialog base size changed to wing length, better for large tip angles
# - corrected harpoon function on simple arrows, and reduced limit to 5.0 (0.5 internal)
# - corrected: undo didn't include selection mask saving

#
# To do
# -----
# - bug: in some cases undo still un-selects the active layer (create layer unchecked)
# - select drawn / not drawn for each element
# - examine visual bug with very short path and reversed-arrow tail (use the whole path 
#    instead of the already cut one?)
# - tail style "composite", where elements are doubled (feather and crossbar, bullet 
#       with point)
# - numbered bullet option (user suggestion)  >> not for now, hard to fit any font 
#    into a given diameter
# - deal with edge cases : 
#   - closed paths (? maybe)
#   - solve layer resizing when "draw arrowheads only" is checked (maybe?)
# - structure code of main routine  >> better for now, still work to do
# - find a way to smooth curve to tangent junction
# - simpler, non interactive version? (arrowhead size determined by last anchor?)


#*************************************************************************************


# imports
#--------
import gi
gi.require_version('Gimp', '3.0')
from gi.repository import Gimp
gi.require_version('GimpUi', '3.0')
from gi.repository import GimpUi
# gi.require_version('Gegl', '0.4')
# from gi.repository import Gegl
from gi.repository import GObject
from gi.repository import GLib

import os
import sys
import math
import time # for testing


#*************************************************************************************


class strokeArrows (Gimp.PlugIn):
    ## GimpPlugIn virtual methods ##
    def do_query_procedures(self):
        return [ "pl-stroke-arrows" ]

    def do_create_procedure(self, name):
        procedure = Gimp.ImageProcedure.new(self, name,
                                            Gimp.PDBProcType.PLUGIN,
                                            drawArrows, None)

        procedure.set_image_types("*")

        procedure.set_menu_label("Stroke arrows ...")
        procedure.set_icon_name(GimpUi.ICON_GEGL)
        procedure.add_menu_path('<Image>/Edit')

        procedure.set_documentation("Plug-in Mon Gabarit",
                                    "Description",
                                    name)
        procedure.set_attribution("Pascal L.", "Pascal L.", "2025")

        # dialog box parameters
        # ---------------------
        choice = Gimp.Choice.new()
        choice.add("filled", 0, "filled", "")
        choice.add("empty",  1, "empty", "")
        choice.add("simple", 2, "simple", "")
        procedure.add_choice_argument("arrowStyle", "Arrowhead style", "Arrowhead style",
                                       choice, "filled", GObject.ParamFlags.READWRITE)
        procedure.add_double_argument("wingLen", "Wing length (px)",
                                    "Length of the wing (px)",
                                    2.0, 500.0, 40.0, GObject.ParamFlags.READWRITE)
        procedure.add_double_argument("tipAngle", "Tip angle (°)",
                                    "Tip angle (°)",
                                    10.0, 120.0, 35.0, GObject.ParamFlags.READWRITE)
        procedure.add_double_argument("harpoonFactor", "Shape (-◆ / ➤+)",
                                    "positive: harpoon / negative: diamond",
                                    -10.0, 5.0, 0.0, GObject.ParamFlags.READWRITE) # concavity? gutter? slenderness? anchor position? shape?
        procedure.add_double_argument("strokeWidth", "Stroke width (px)",
                                    "Stroke width (px)",
                                    0.0, 50.0, 4.0, GObject.ParamFlags.READWRITE)
        choice = Gimp.Choice.new()
        choice.add("none", 0, "none", "")
        choice.add("crossbar", 1, "bar", "") # (transversal) line/stop? stroke? cross-line? crossbar?
        choice.add("bullet", 2, "bullet", "")
        choice.add("feathered", 3, "feather", "")
        choice.add("arrowhead",  4, "two-way arrow", "") # opposite? backward? reversed? two-way?
        procedure.add_choice_argument("tailType", "Tail type", "Tail type",
                                       choice, "none", GObject.ParamFlags.READWRITE)
        choice = Gimp.Choice.new()
        choice.add("default", 0, "same as arrowhead", "")
        choice.add("filled", 1, "filled", "")
        choice.add("empty", 2, "empty", "")
        choice.add("simple",  3, "simple", "")
        procedure.add_choice_argument("tailStyle", "Tail style", "Tail style",
                                       choice, "default", GObject.ParamFlags.READWRITE)
        procedure.add_double_argument("tailSize", "Tail width",
                                    "Tail width (px)",
                                    2.0, 500.0, 80.0, GObject.ParamFlags.READWRITE)
        choice = Gimp.Choice.new()
        choice.add("relative", 0, "relative (%)", "")
        choice.add("absolute", 1, "absolute (px)", "")
        procedure.add_choice_argument("tailUnit", "Tail width unit", "Tail width unit",
                                       choice, "relative", GObject.ParamFlags.READWRITE)
        procedure.add_boolean_argument("createLayer", "Create new layer",
                                    "Create new layer", True, GObject.ParamFlags.READWRITE)
        procedure.add_boolean_argument("arrowHeadOnly", "Remove shaft, draw head",
                                    "Remove shaft, draw arrowhead", False, GObject.ParamFlags.READWRITE)
        procedure.add_boolean_argument("arrowTailOnly", "Remove shaft, draw tail",
                                    "Remove shaft, draw tail", False, GObject.ParamFlags.READWRITE)
        procedure.add_boolean_argument("invertPath", "Flip direction",
                                    "Flip direction", False, GObject.ParamFlags.READWRITE)
        procedure.add_boolean_argument("keepPaths", "Keep newly created paths",
                                    "Keep newly created paths", False, GObject.ParamFlags.READWRITE)

        return procedure


#*************************************************************************************


# main routine
#--------------

def drawArrows(procedure, run_mode, monImage, drawables, config, data):
    
    
    # user dialog
    # ************
    
    if run_mode == Gimp.RunMode.INTERACTIVE:
        GimpUi.init('python-fu-pl-gabarit') # ou nom du fichier

        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        else:
            dialog.destroy()

    # parameters list for user dialog
    # -------------------------------
    
    arrowStyle      = config.get_property("arrowStyle")
    strokeWidth     = config.get_property("strokeWidth")
    wingLen        = config.get_property("wingLen")
    tipAngle        = config.get_property("tipAngle")
    harpoonFactor   = config.get_property("harpoonFactor")
    tailType        = config.get_property("tailType")
    tailStyle       = config.get_property("tailStyle")
    tailSize        = config.get_property("tailSize")
    tailUnit        = config.get_property("tailUnit")
    createLayer     = config.get_property("createLayer")
    arrowHeadOnly   = config.get_property("arrowHeadOnly")
    arrowTailOnly   = config.get_property("arrowTailOnly")
    invertPath      = config.get_property("invertPath")
    keepPaths       = config.get_property("keepPaths")

    # user dialog variables (for testing)
    # -----------------------------------
    # arrowStyle      = "filled" # "filled", "empty", "simple"
    # strokeWidth     =  4.0
    # wingLen         = 40.0
    # tipAngle        = 35.0 # deg
    # harpoonFactor   =  2.0 # 0.0 - ~6.0 : harpoon / 0.0: flat / 0.0 - -10.0 : diamond
    # tailType        = "none"
    # tailStyle       = "default"
    # tailSize        = 20.0
    # tail unit       = "relative"
    # createLayer     = True
    # arrowHeadOnly   = False
    # arrowTailOnly   = False
    # invertPath      = False
    # keepPaths       = False
    
    # Undo and context
    # ****************
    
    monImage.undo_group_start()
    Gimp.context_push()
    
    # Gimp.context_set_defaults()
    # Gimp.context_set_foreground(fgColor)
    
    Gimp.context_set_antialias(True)
    Gimp.context_set_feather(False)
    
    Gimp.context_set_line_width(strokeWidth)
    Gimp.context_set_line_join_style(0) # MITER
    Gimp.context_set_line_cap_style(0)  # BUTT
    Gimp.context_set_stroke_method(0)   # LINE
    Gimp.context_set_line_miter_limit(100.0) # max value accepted by GIMP: 100.0
    
    # Initialisations
    # ***************
    
    selectedPaths       = monImage.get_selected_paths()
    thisSelection       = monImage.get_selection()
    savedSelection      = thisSelection.save(monImage)
    
    # adjustments to user parameters
    # ------------------------------
    
    if tailStyle == "default" :
        tailStyle = arrowStyle
    # end if
    
    tipAngle            = math.radians(tipAngle)       # convert from user friendly
    harpoonFactor       = 1.0 - (harpoonFactor / 10.0) # convert from user friendly
    
    # get arrow length from wing length entered in the UI
    arrowLen = math.cos( tipAngle / 2.0 ) * wingLen # arrowLen is used from here
    
    # for diamond shapes, we adjust the reference length
    if harpoonFactor > 1.0 :
        weight = 0.15
        ratio = 1.0 + (harpoonFactor - 1.0) * weight
        arrowLen = arrowLen / ratio # mitigated for optical reasons
        tailSize *= ratio # we want to keep the same relative tail size
    # end if
    
    # arrowLength can change, arrowLen stays constant from there
    arrowLength = arrowLen
    
    if tailUnit == "relative" :
        refSize = 2.0 * math.tan(0.5 * tipAngle) * arrowLength # reference size from arrowhead width
        tailSize = tailSize / 100.0 * refSize
    
    # for feather types other than simple, we adjust the reference size (used as width)
    # not active, keep just in case
    # if tailType == "feathered" and tailStyle != "simple" :
        # tailSize /= 1.25
    
    # CONSTANTS
    harpThreshold = 0.7  # harpoon factor under which cut point and anchor point become distinct
    
    if arrowStyle == "simple" :
        harpThreshold = 0.9
    
    deltaT        = 0.01 # increment of t parameter used to scan segments
    
    # get active layer
    # ----------------
    
    if createLayer == True :
        
        sourceDrawable = Gimp.Layer.new(monImage, "Arrows #0", monImage.get_width(), monImage.get_height(), 
                                    monImage.get_base_type() * 2 + 1, 100.0, 28) # 28:normal
        monImage.insert_layer(sourceDrawable, None, 0)
        
    elif len(drawables) != 1:
        
        Gimp.context_pop()
        monImage.undo_group_end()
        msg = "Procedure '{}' only works with one drawable.".format(procedure.get_name())
        error = GLib.Error.new_literal(Gimp.PlugIn.error_quark(), msg, 0)
        return procedure.new_return_values(Gimp.PDBStatusType.CALLING_ERROR, error)
        
    else:
        
        sourceDrawable = drawables[0]
            
    # end if
    
    #*********************************************************************************
    
    #***********
    # Main code
    #***********
    
    # accumulatedCalcTime = 0 # debug
    
    userPaths = monImage.get_selected_paths()
    
    # no path selected
    if userPaths == [] :
        
        Gimp.context_pop()
        monImage.undo_group_end()
        msg = "Procedure '{}' needs at least one path".format(procedure.get_name())
        error = GLib.Error.new_literal(Gimp.PlugIn.error_quark(), msg, 0)
        return procedure.new_return_values(Gimp.PDBStatusType.CALLING_ERROR, error)
    # end if
    
    #--------------------------
        
    wingLength = arrowLength / math.cos( tipAngle / 2.0 )
    axisLength = harpoonFactor * arrowLength
    # find anchor placement of the head, curve cut point must not be past harpThreshold * arrowLength
    cutDistance = max( 0.0, ( harpThreshold - harpoonFactor ) * arrowLength ) # added distance to cut point
    
    # for styles with contour, we reduce arrow size
    tipProtruding, arrowLength, axisLength, wingLength = shrinkArrowhead(arrowStyle, strokeWidth, tipAngle, 
                                                arrowLength, axisLength, wingLength)
    
    # same for arrow tail
    if tailType == "arrowhead" :
        
        tailArrowLength = arrowLen
        
        tailWingLength = tailArrowLength / math.cos( tipAngle / 2.0 )
        tailAxisLength = harpoonFactor * tailArrowLength
        tailCutDistance = max( 0.0, ( harpThreshold - harpoonFactor ) * tailArrowLength )
        
        tailTipProtruding, tailArrowLength, tailAxisLength, tailWingLength = shrinkArrowhead(tailStyle, 
                                strokeWidth, tipAngle, tailArrowLength, tailAxisLength, tailWingLength)
        
    elif ( tailType == "bullet" and tailStyle != "filled" 
        or tailType == "feathered" and tailStyle == "empty" ) :
        
        tailSize = max( tailSize - strokeWidth, 2.0 )
        
    #end if
    
    
    
    # MAIN LOOP - work on each selected path successively
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    
    for thisPath in userPaths :
        
        # time1 = time.perf_counter() # debug
        
        # get last stroke and error handling
        # ----------------------------------
        
        allStrokes = thisPath.get_strokes()
        
        if allStrokes == [] :
            Gimp.context_pop()
            monImage.undo_group_end()
            msg = "Paths must have at least one stroke".format(procedure.get_name())
            error = GLib.Error.new_literal(Gimp.PlugIn.error_quark(), msg, 0)
            return procedure.new_return_values(Gimp.PDBStatusType.CALLING_ERROR, error)
        # end if
        
        thisStroke = allStrokes[-1]
        
        # get the path in GIMP format
        flatPointsList = thisPath.stroke_get_points(thisStroke)[1]
        
        if len(flatPointsList) == 6 :
            Gimp.context_pop()
            monImage.undo_group_end()
            msg = "The last point of this path is not connected".format(procedure.get_name())
            error = GLib.Error.new_literal(Gimp.PlugIn.error_quark(), msg, 0)
            return procedure.new_return_values(Gimp.PDBStatusType.CALLING_ERROR, error)
        # end if
        
        # convert coords list to points list
        pointsList = listToPoints(flatPointsList)
        
        if invertPath == True :
            pointsList.reverse()
        # end if
        
        # get the new shortened and prepared path for the arrowhead
        # ---------------------------------------------------------
        
        newPointsList, axisLength, anchorX, anchorY, endAngle = designPath(arrowStyle, 
                                    strokeWidth, pointsList, arrowLength, axisLength, 
                                    harpoonFactor, cutDistance, tipProtruding, deltaT)
                                    
        # print("cut distance", cutDistance) # debug
        
        #*****************************************************************************
        
        # arrow tail
        # ----------
        
        if tailType == "crossbar" :
            
            endX, endY = newPointsList[0]
            tanX, tanY = newPointsList[1]
            
            if endX == tanX : # avoid division by 0, find a true tangent
                tempPoints = newPointsList[0:4]
                tempPoints = sliceBezier(tempPoints, 0.1)
                tanX, tanY = tempPoints[2] # we take the third point!
                # print(tempPoints) # debug
            # end if
            
            tailAngle = math.atan( ( endY - tanY ) / ( endX - tanX ) )
            if endX - tanX < 0.0 :
                tailAngle += math.pi # invert from atan result
            # end if
            
            tailPath = buildCrossbar(monImage, endX, endY, tailAngle, tailSize)
        
        # bullet
        elif tailType == "bullet" :
            
            oriX, oriY = newPointsList[0]
            
            if tailStyle == "empty" :
                
                reversdPointsList = newPointsList.copy()
                reversdPointsList.reverse()
                newPointsList, placeHolder, tailCutDistance = shortenSpline(reversdPointsList, 
                                                            tailSize / 2.0, 0.0, 0.0, deltaT)
                newPointsList.reverse()
            
            tailPath = buildBullet(monImage, oriX, oriY, tailSize)
            
        # feathered
        elif tailType == "feathered" and ( tailStyle == "filled" or tailStyle == "empty" ) :
            
            reversdPointsList = newPointsList.copy()
            reversdPointsList.reverse()
            newPointsList, tailSize, tailCutDistance = shortenSpline(reversdPointsList, tailSize, 0.0, 0.0, deltaT)
            
            cutX, cutY = newPointsList[-1]
            tanX, tanY = newPointsList[-2]
            
            tailAngle = math.atan( ( cutY - tanY ) / ( cutX - tanX ) )
            if cutX - tanX < 0.0 :
                tailAngle += math.pi # invert from atan result
            # end if
            
            newPointsList = buildPatch(newPointsList, tailSize, cutX, cutY, tailAngle)
            tailPath = buildFeather(monImage, tailSize, cutX, cutY, tailAngle)
            newPointsList.reverse()
            
        # simple feather
        elif tailType == "feathered" and tailStyle == "simple" :
            
            reversdPointsList = newPointsList.copy()
            reversdPointsList.reverse()
            
            n = 2 # number of wings (2 - 5)
            tailLength = (2.0 * strokeWidth + tailSize / 2.5 + 1.0) * float(n-1) / 2.0
            
            # tailCutDistance unused
            newPointsList, tailLength, tailCutDistance = shortenSpline(reversdPointsList, tailLength, 0.0, 0.0, deltaT)
            
            cutX, cutY = newPointsList[-1]
            tanX, tanY = newPointsList[-2]
            
            tailAngle = math.atan( ( cutY - tanY ) / ( cutX - tanX ) )
            if cutX - tanX < 0.0 :
                tailAngle += math.pi # invert from atan result
            # end if
            
            clearSegments = 1 # max: n-1, number of intervals not drawn between wings
            patchReduction = 1.0 - float(clearSegments) / float(n-1)
            patchSize = tailLength * patchReduction
            
            newPointsList = buildPatch(newPointsList, patchSize, cutX, cutY, tailAngle)
            tailPath = buildSimpleFeather(monImage, tailSize, cutX, cutY, tailLength, tailAngle, n)
            newPointsList.reverse()
            
        # backwards arrowhead
        elif tailType == "arrowhead" :
            
            reversdPointsList = newPointsList.copy()
            reversdPointsList.reverse()
            
            newPointsList, tailAxisLength, tailAnchorX, tailAnchorY, tailEndAngle = designPath(tailStyle, 
                                    strokeWidth, reversdPointsList, tailArrowLength, tailAxisLength, 
                                    harpoonFactor, tailCutDistance, tailTipProtruding, deltaT)
            
            # print("tail cut distance", tailCutDistance) # debug
            
            tailPath = buildArrowhead(monImage, tailStyle, tailAxisLength, tailArrowLength, 
                                    tailWingLength, tailAnchorX, tailAnchorY, tipAngle, tailEndAngle)
            
            newPointsList.reverse()
            
        #end if
        
        #*****************************************************************************
        
        # complete the path and prepare for GIMP format
        # ---------------------------------------------
        
        newFlatList = flattenPoints(newPointsList)
        newFlatList.insert(0, newFlatList[0])
        newFlatList.insert(1, newFlatList[2])
        newFlatList.extend(newFlatList[-2:])
        
        # print(newFlatList) # debug
        
        # create path
        newPath = Gimp.Path.new(monImage, "body path #1")
        newPath.stroke_new_from_points(0, newFlatList, False)
        
        monImage.insert_path(newPath, None, 0)
        
        # ****************************************************************************
        
        # build arrowhead
        arrowPath = buildArrowhead(monImage, arrowStyle, axisLength, arrowLength, wingLength, 
                                    anchorX, anchorY, tipAngle, endAngle)
        
        # ****************************************************************************
        
        # stroke the body
        # ---------------
        
        if arrowHeadOnly == False and arrowTailOnly == False :
            
            sourceDrawable.edit_stroke_item(newPath)
        
        # end if
        
        # ****************************************************************************
        
        # fill or stroke the arrowhead
        # ----------------------------
        
        if not ( arrowHeadOnly == False and arrowTailOnly == True ) : # then we draw head
            
            if arrowStyle == "filled" :
                
                # todo: function
                if Gimp.Selection.is_empty(monImage) :
                    monImage.select_item(2, arrowPath) # 2: replace
                else :
                    monImage.select_item(3, arrowPath) # 3: intersect
                    
                if Gimp.Selection.is_empty(monImage) == False :
                    sourceDrawable.edit_fill(0) # 0: FG color
                    
                monImage.select_item(2, savedSelection)
                
            else :
                
                sourceDrawable.edit_stroke_item(arrowPath)
                
            # end if
        
        # fill or stroke the arrow tail
        # -----------------------------
        
        if tailType != "none" and not ( arrowTailOnly == False 
                                        and arrowHeadOnly == True ) : # then we draw tail
            
            if tailStyle == "filled" and tailType != "crossbar" :
                
                if Gimp.Selection.is_empty(monImage) :
                    monImage.select_item(2, tailPath) # 2: replace
                else :
                    monImage.select_item(3, tailPath) # 3: intersect
                    
                if Gimp.Selection.is_empty(monImage) == False :
                    sourceDrawable.edit_fill(0) # 0: FG color
                    
                monImage.select_item(2, savedSelection)
                
            else :
                
                sourceDrawable.edit_stroke_item(tailPath)
                
            # end if
        # end if
        
        # clean unwanted paths
        # --------------------
        if keepPaths == False :
            
            monImage.remove_path(newPath)
            monImage.remove_path(arrowPath)
            if tailType != "none" :
                monImage.remove_path(tailPath)
            # end if
            
        # end if
        
    # END OF MAIN LOOP
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    
    
    # crop if new layer
    # -----------------
    
    if createLayer == True :
        
        monImage.select_item(2, sourceDrawable)
        boundingBox = Gimp.Selection.bounds(monImage)
        # print("bounds : " + str(boundingBox)) # debug
        offsetX = -boundingBox[2] # no idea why negative
        offsetY = -boundingBox[3]
        width = boundingBox[4] - boundingBox[2]
        height = boundingBox[5] - boundingBox[3]
        
        sourceDrawable.resize(width, height, offsetX, offsetY)
        
    # end if
    
    #*********************************************************************************

    # Finalisations
    # *************

    monImage.select_item(2, savedSelection)
    monImage.remove_channel(savedSelection)
    monImage.set_selected_paths(selectedPaths)
    
    if sourceDrawable.is_layer() :
        monImage.set_selected_layers([sourceDrawable])
    elif sourceDrawable.is_channel() or sourceDrawable.is_layer_mask() :
        monImage.set_selected_channels([sourceDrawable])
    
    Gimp.context_pop()
    monImage.undo_group_end()
    
    
    # print("calc time:", accumulatedCalcTime) # debug
    
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


#*************************************************************************************
#*************************************************************************************


def buildArrowhead(monImage, arrowStyle, axisLength, arrowLength, wingLength, 
                    anchorX, anchorY, tipAngle, endAngle) :
    
    # construct the arrowhead
    # -----------------------
    
    tipX = anchorX + math.cos(endAngle) * axisLength
    tipY = anchorY + math.sin(endAngle) * axisLength
    
    point1X = tipX - wingLength * math.cos( endAngle + tipAngle/2 )
    point1Y = tipY - wingLength * math.sin( endAngle + tipAngle/2 )
    point2X = tipX - wingLength * math.cos( endAngle - tipAngle/2 )
    point2Y = tipY - wingLength * math.sin( endAngle - tipAngle/2 )
    
    if arrowStyle == "filled" or arrowStyle == "empty" :
        
        arrowHeadPoints = [
                    tipX,
                    tipY,
                    tipX,
                    tipY,
                    tipX,
                    tipY,
                    point1X,
                    point1Y,
                    point1X,
                    point1Y,
                    point1X,
                    point1Y,
                    anchorX,
                    anchorY,
                    anchorX,
                    anchorY,
                    anchorX,
                    anchorY,
                    point2X,
                    point2Y,
                    point2X,
                    point2Y,
                    point2X,
                    point2Y
                    ]
        
        arrowPath = Gimp.Path.new(monImage, "arrow head #1")
        arrowPath.stroke_new_from_points(0, arrowHeadPoints, True)
        
    elif arrowStyle == "simple" :
        
        arrowHeadPoints = [
                    point1X,
                    point1Y,
                    point1X,
                    point1Y,
                    point1X,
                    point1Y,
                    tipX,
                    tipY,
                    tipX,
                    tipY,
                    tipX,
                    tipY,
                    point2X,
                    point2Y,
                    point2X,
                    point2Y,
                    point2X,
                    point2Y
                    ]
        
        arrowPath = Gimp.Path.new(monImage, "arrow head #1")
        arrowPath.stroke_new_from_points(0, arrowHeadPoints, False)
        
    # end if
    
    monImage.insert_path(arrowPath, None, 0)
    
    return arrowPath
    
#*************************************************************************************


def buildCrossbar(monImage, oriX, oriY, tailAngle, tailSize) :
    
    point1X = oriX + math.cos(tailAngle + math.pi * 0.5) * tailSize * 0.5
    point1Y = oriY + math.sin(tailAngle + math.pi * 0.5) * tailSize * 0.5
    point2X = oriX + math.cos(tailAngle - math.pi * 0.5) * tailSize * 0.5
    point2Y = oriY + math.sin(tailAngle - math.pi * 0.5) * tailSize * 0.5
    
    crossbarPoints = [
                    point1X,
                    point1Y,
                    point1X,
                    point1Y,
                    point1X,
                    point1Y,
                    point2X,
                    point2Y,
                    point2X,
                    point2Y,
                    point2X,
                    point2Y
                    ]
    
    tailPath = Gimp.Path.new(monImage, "arrow tail #1")
    tailPath.stroke_new_from_points(0, crossbarPoints, False)
    monImage.insert_path(tailPath, None, 0)
    
    return tailPath


#*************************************************************************************


def buildBullet(monImage, oriX, oriY, tailSize) :
    
    radius = tailSize / 2.0
    
    tailPath = Gimp.Path.new(monImage, "arrow tail #1")
    tailPath.bezier_stroke_new_ellipse(oriX, oriY, radius, radius, 0.0)
    
    monImage.insert_path(tailPath, None, 0)
    
    return tailPath

#*************************************************************************************


def buildFeather(monImage, tailWidth, anchorX, anchorY, tailAngle) :
    
    tailWidth /= 2.0
    wingAngle = math.pi / 4.0
    lengthRatio = 2.0
    tailLength = lengthRatio * tailWidth
    wingLength = tailWidth / math.cos(wingAngle)
    
    point1X = anchorX + wingLength * math.cos(tailAngle + wingAngle)
    point1Y = anchorY + wingLength * math.sin(tailAngle + wingAngle)
    point2X = point1X + tailLength * math.cos(tailAngle)
    point2Y = point1Y + tailLength * math.sin(tailAngle)
    
    point3X = anchorX + tailLength * math.cos(tailAngle)
    point3Y = anchorY + tailLength * math.sin(tailAngle)
    
    point5X = anchorX + wingLength * math.cos(tailAngle - wingAngle)
    point5Y = anchorY + wingLength * math.sin(tailAngle - wingAngle)
    point4X = point5X + tailLength * math.cos(tailAngle)
    point4Y = point5Y + tailLength * math.sin(tailAngle)
    
    featherPoints = [
                    anchorX,
                    anchorY,
                    anchorX,
                    anchorY,
                    anchorX,
                    anchorY,
                    point1X,
                    point1Y,
                    point1X,
                    point1Y,
                    point1X,
                    point1Y,
                    point2X,
                    point2Y,
                    point2X,
                    point2Y,
                    point2X,
                    point2Y,
                    point3X,
                    point3Y,
                    point3X,
                    point3Y,
                    point3X,
                    point3Y,
                    point4X,
                    point4Y,
                    point4X,
                    point4Y,
                    point4X,
                    point4Y,
                    point5X,
                    point5Y,
                    point5X,
                    point5Y,
                    point5X,
                    point5Y
                    ]
                    
    tailPath = Gimp.Path.new(monImage, "arrow tail #1")
    tailPath.stroke_new_from_points(0, featherPoints, True)
    monImage.insert_path(tailPath, None, 0)
    
    return tailPath
    

#*************************************************************************************


def buildSimpleFeather(monImage, tailWidth, anchorX, anchorY, tailLength, tailAngle, n) :
    
    tailWidth /= 2.0
    wingAngle = math.pi / 4.0
    wingLength = tailWidth / math.sin(wingAngle)
    reduction = 0.1 * wingLength
    
    tailPath = Gimp.Path.new(monImage, "arrow tail #1")
    
    i = 0
    
    while i <= n - 1 :
        
        wingRatio = float(i) / float(n-1)
        thisWingLength = wingLength * ( 0.8 - ( 0.75 * math.sqrt(float(n) / 4.0) * wingRatio )**2.0 + 0.2**2.0 ) # 0.775
        
        point1X = anchorX + thisWingLength * math.cos(tailAngle + wingAngle)
        point1Y = anchorY + thisWingLength * math.sin(tailAngle + wingAngle)
        point2X = anchorX + thisWingLength * math.cos(tailAngle - wingAngle)
        point2Y = anchorY + thisWingLength * math.sin(tailAngle - wingAngle)
        
        featherPoints = [
                        point1X,
                        point1Y,
                        point1X,
                        point1Y,
                        point1X,
                        point1Y,
                        anchorX,
                        anchorY,
                        anchorX,
                        anchorY,
                        anchorX,
                        anchorY,
                        point2X,
                        point2Y,
                        point2X,
                        point2Y,
                        point2X,
                        point2Y
                        ]
        
        tailPath.stroke_new_from_points(0, featherPoints, False)
        
        anchorX += math.cos(tailAngle) * tailLength / (float(n)-1)
        anchorY += math.sin(tailAngle) * tailLength / (float(n)-1)
        
        
        i += 1
        # wingLength -= reduction * float(i)
        
    # end while
    
    monImage.insert_path(tailPath, None, 0)
    
    return tailPath
    

#*************************************************************************************


# distance between two points
def distance(p1, p2) :
    
    dist = math.hypot(p2[1] - p1[1], p2[0] - p1[0])
    
    return dist


#*************************************************************************************


# convert coords list to points list
def listToPoints(flatPointsList) :
    
    last = len(flatPointsList) / 2 - 1
    i = 1
    pointsList = []
    
    while i < last :
        
        thisPoint = [flatPointsList[2*i], flatPointsList[2*i+1]]
        pointsList.append(thisPoint)
        i += 1
        
    # end while

    return pointsList

#*************************************************************************************


# flatten points list to list of coordinates for GIMP path format
def flattenPoints(pointsList) :
    
    flatList = []
    
    for thisPoint in pointsList :
        
        flatList += thisPoint
        
    # end for
    
    return flatList


#*************************************************************************************


def shrinkArrowhead(style, strokeWidth, tipAngle, arrowLength, axisLength, wingLength) :
    
    alpha = tipAngle / 2.0
    
    if style == "simple" :
        
        tipProtruding = strokeWidth * 0.5 / math.sin(alpha)
        wingProtruding = 0.0
        ratio = ratio = max(arrowLength - tipProtruding, 2.0) / arrowLength
        
    elif style == "empty" :
        
        tipProtruding = strokeWidth * 0.5 / math.sin(alpha)
        
        # print("alpha", alpha, "axis", axisLength, "wing", wingLength) # debug
        
        # wing / back protruding
        if arrowLength == axisLength : # harpoon factor of 1.0
            wingProtruding = 0.5 * strokeWidth
            
        if arrowLength > axisLength :
            gamma = math.atan(math.sin(alpha) / ( math.cos(alpha) - axisLength/wingLength ) )
            wingProtruding = ( 0.5 * strokeWidth * math.cos( 0.5 * (gamma + alpha) ) 
                                                 / math.sin( 0.5 * (gamma - alpha) ) )
            ratio = max(arrowLength - tipProtruding - wingProtruding, 2.0) / arrowLength
            
        else  : # arrowLength < axisLength
            a = axisLength - arrowLength
            b = wingLength * math.sin(alpha)
            wingProtruding = strokeWidth * 0.5 * math.sqrt( pow(a / b, 2.0) + 1.0 )
            ratio = max(axisLength - tipProtruding - wingProtruding, 2.0) / axisLength
            
        # end if
        
        
    else :
        tipProtruding = 0.0
        wingProtruding = 0.0
        ratio = 1.0
    # end if
    
    # print("tip prot.", tipProtruding, "wing prot.", wingProtruding, "length", arrowLength * ratio) # debug
    
    return tipProtruding, arrowLength * ratio, axisLength * ratio, wingLength * ratio

#*************************************************************************************


def designPath(arrowStyle, strokeWidth, pointsList, arrowLength, axisLength, harpoonFactor, 
                cutDistance, tipProtruding, deltaT) :
    
    # print("arrow style:", arrowStyle) # debug
    
    # get the new spline cut at the right place
    # -----------------------------------------
    
    newPointsList, axisLength, cutDistance = shortenSpline(pointsList, axisLength, 
                                                        cutDistance, tipProtruding, deltaT)
    
    cutX, cutY = newPointsList[-1]
    tanX, tanY = newPointsList[-2]
    # print(newPointsList) # debug
    
    # determine the path angle at cut point
    # ----------------------------------------
    
    if cutX == tanX and cutY > tanY :
        endAngle = math.pi * 0.5
    elif cutX == tanX and cutY < tanY :
        endAngle = math.pi * 1.5
    else :
        endAngle = math.atan( ( cutY - tanY ) / ( cutX - tanX ) )
    # end if
    
    if cutX < tanX :
        endAngle += math.pi # invert from atan result
    # end if
    
    # anchor point of the arrowhead
    
    anchorX = cutX + math.cos(endAngle) * cutDistance
    anchorY = cutY + math.sin(endAngle) * cutDistance
    
    # add a patch at anchor point to remove visible spacing between head and body
    # ----------------------------------------------------------------------------
    # (todo: define function for that...)
    
    if arrowStyle == "simple" :
        
        patchLength = arrowLength / 2.0 - strokeWidth / 2.0 # changed from ... - strokeWidth
        # todo: limit patch length
        
    elif arrowStyle == "filled" : 
        
        patchLength = harpoonFactor**2 * strokeWidth
        
    else :
        
        patchLength = 0.0
    
    # end if
    
    patchLength += cutDistance
    
    if patchLength > 0.0 :
        
        newPointsList = buildPatch(newPointsList, patchLength, cutX, cutY, endAngle)
    
    # end if
    
    return newPointsList, axisLength, anchorX, anchorY, endAngle


#*************************************************************************************


def buildPatch(pointsList, patchLength, cutX, cutY, endAngle) :
    
    patchEndX   = cutX + math.cos(endAngle) * patchLength
    patchEndY   = cutY + math.sin(endAngle) * patchLength
    
    patchPathPoints = [
                [cutX, cutY],
                [patchEndX, patchEndY],
                [patchEndX, patchEndY]
                ]

    pointsList.extend(patchPathPoints)
    
    return pointsList


#*************************************************************************************


def shortenSpline(pointsList, axisLength, cutDistance, tipProtruding, deltaT) :
    
    n = (len(pointsList) - 1) / 3 # segments number of spline
    u = float(n)          # intitial u, parameter used to find points along the spline
    cumulDist = 0.0
    lastP = pointsList[-1]
    targetLength = axisLength + cutDistance + tipProtruding
    
    counter = 0                 # debug
    time1 = time.perf_counter() # time debug
    
    # deltaL = 0.0 # fallback
    
    while cumulDist < targetLength and u > deltaT :
        
        u -= deltaT
        currentP = getCutSegmt(pointsList, u)[-1]
        deltaL = distance(lastP, currentP)
        cumulDist += deltaL
        lastP = currentP
        counter += 1
        
    # end while
    
    # print("deltaL:", deltaL) # debug
    
    if u <= deltaT :  # u too close from the start point
        
        if cumulDist <= cutDistance :   
            cutDistance -= targetLength - cumulDist  # then we shrink cutLength instead
        else :
            axisLength -= targetLength - cumulDist + cutDistance
            cutDistance = 0.0
            
    else :
        ratioOvershoot = (cumulDist - targetLength) / deltaL # by how much targetLength is overshot
        u += deltaT * ratioOvershoot                         # correct u by this small bit
    # end if
    
    # print("iterations:", counter)        # debug
    # time2 = time.perf_counter()     # time debug
    # print("time:", time2 - time1)   # time debug
    
    # we get the last segment
    lastSegment = getCutSegmt(pointsList, u)
    
    segmentID = math.trunc(u) # int
    newPointsList = pointsList[0 : segmentID * 3] + lastSegment
    
    return newPointsList, axisLength, cutDistance
    
    
#*************************************************************************************


# returns the segment cut at u position
def getCutSegmt(pointsList, u) :
    
    segmentID = math.trunc(u) # int
    t = u - float(segmentID) # other sol: = u % 1
    
    segStart = 3 * segmentID
    segment = pointsList[segStart : segStart + 4] # segment of interest
    
    splitSeg = sliceBezier(segment, t)[0:4]
    
    return splitSeg


#*************************************************************************************


# https://stackoverflow.com/questions/8369488/splitting-a-bezier-curve/8405756#8405756

def sliceBezier(points, t): # 4 point sous forme [ [x1, y1], [x2, y2],... ]
    
    p1, p2, p3, p4 = points
    x1, y1 = p1
    x2, y2 = p2
    x3, y3 = p3
    x4, y4 = p4

    x12 = (x2-x1)*t+x1
    y12 = (y2-y1)*t+y1

    x23 = (x3-x2)*t+x2
    y23 = (y3-y2)*t+y2

    x34 = (x4-x3)*t+x3
    y34 = (y4-y3)*t+y3

    x123 = (x23-x12)*t+x12
    y123 = (y23-y12)*t+y12

    x234 = (x34-x23)*t+x23
    y234 = (y34-y23)*t+y23

    x1234 = (x234-x123)*t+x123
    y1234 = (y234-y123)*t+y123

    return [ [x1, y1], [x12, y12], [x123, y123], [x1234, y1234], [x234, y234], [x34, y34], [x4, y4] ]


#*************************************************************************************


Gimp.main(strokeArrows.__gtype__, sys.argv)

