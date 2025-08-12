#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Description du script
#
# Original author : Pascal L.
# Version 0.5 for GIMP 3.0

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
# - dealt with case when second last anchor is too close to the end
# - changed (user) scale and renamed harpoon factor to "anchor point position"
# - extended stroke for better contact between head and body
# - corrected an issue with incorrect direction calculation in edge cases, by using 
#       dot product (obsolete)
# - checked case where path is too short - clean error report still to figure out
# - shrink and displace arrow head for empty and simple
# - option to create new layer
# - prepared for exact calculation of anchor point and tangents, not yet plugged in
# - take existing selection correctly into account
# - limited positive harpoon factor to 6
#
# 0.3 :
# - plugged in exact calculation of anchor point and tangents (Bezier)
# - adapted anchor angle calculation
# - target segment detection more robust, as some edge cases failed to find the target
#
# 0.4 :
# - refactored the anchor Bezier search to include an arbitrary number of segment. 
#   In case of failure, the search starts again with more segments.
# - better error management (no path, break from loops...)
# - defined pointy corner limit for empty and simple
# - reselected current layer at the end
#
# 0.5 :
# - added the patch at the end of the body (not just as another joint stroke)
# - cleaned code
# - context for stroke (not global: let user change FG)
# - general changes from coord lists to points lists
# - implemented standard Bezier search algorithm with 5 points and distances
#   - above fixes bug with bug_strokeArrows_04.xcf
#   - added bigger increment at each try for number of segments, fixes bug_strokeArrows_05.xcf
# - many bug fixes after the algorithm and points lists refactoring
# - changed menu location from "Tools" to "Edit".
#
# To do
# -----
# - arrows at both ends                                     - future
# - "revert path" checkbox (first step for arrows at both ends)
# - deal with edge cases : 
#   - closed paths (? maybe)
# - get better placement of anchor point for simple arrows
# - write own distance eval function
# - write and try own Bezier research algorithm based on segments (for fun)
# - better code structure of main routine, which is barely readable


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

        # paramètres de la boite de dialogue
        # ----------------------------------
        choice = Gimp.Choice.new()
        choice.add("filled", 0, "filled", "")
        choice.add("empty",  1, "empty", "")
        choice.add("simple", 2, "simple", "")
        procedure.add_choice_argument("arrowStyle", "Arrowhead style", "Arrowhead style",
                                       choice, "filled", GObject.ParamFlags.READWRITE)
        procedure.add_double_argument("strokeWidth", "Stroke width (px)",
                                    "Stroke width (px)",
                                    0.0, 50.0, 4.0, GObject.ParamFlags.READWRITE)
        procedure.add_double_argument("arrowLength", "Arrowhead length (px)",
                                    "Arrow head size (px)",
                                    2.0, 500.0, 40.0, GObject.ParamFlags.READWRITE)
        procedure.add_double_argument("tipAngle", "Tip angle (°)",
                                    "Tip angle (°)",
                                    10.0, 120.0, 35.0, GObject.ParamFlags.READWRITE)
        procedure.add_double_argument("harpoonFactor", "Anchor offset",
                                    "positive: harpoon / negative: diamond",
                                    -10.0, 6.0, 0.0, GObject.ParamFlags.READWRITE)
        procedure.add_boolean_argument("arrowHeadOnly", "Draw arrowheads only",
                                    "Draw arrowheads only", False, GObject.ParamFlags.READWRITE)
        procedure.add_boolean_argument("createLayer", "Create new layer",
                                    "Create new layer", True, GObject.ParamFlags.READWRITE)
        procedure.add_boolean_argument("keepPaths", "Keep paths",
                                    "Keep paths", False, GObject.ParamFlags.READWRITE)

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
    arrowLength     = config.get_property("arrowLength")
    tipAngle        = config.get_property("tipAngle")
    harpoonFactor   = config.get_property("harpoonFactor")
    arrowHeadOnly   = config.get_property("arrowHeadOnly")
    createLayer     = config.get_property("createLayer")
    keepPaths       = config.get_property("keepPaths")

    # user dialog variables (for testing)
    # -----------------------------------
    # arrowStyle      = "filled" # "filled", "empty", "simple"
    # strokeWidth     =  4.0
    # arrowLength     = 40.0
    # tipAngle        = 35.0 # deg
    # harpoonFactor   =  2.0 # 0.0 - ~6.0 : harpoon / 0.0: flat / 0.0 - -10.0 : diamond
    # keepPaths       = False
    # createLayer     = True
    # arrowHeadOnly   = True
    
    # Initialisations
    # ***************
    
    selectedPaths       = monImage.get_selected_paths()
    thisSelection       = monImage.get_selection()
    savedSelection      = thisSelection.save(monImage)
    
    tipAngle            = math.radians(tipAngle)       # convert from user friendly
    harpoonFactor       = 1.0 - (harpoonFactor / 10.0) # convert from user friendly
    tipProtruding       = strokeWidth / 2.0 / math.sin( tipAngle / 2.0 )
    
    # for styles with contour, we reduce arrow size
    if arrowStyle == "empty" or arrowStyle == "simple" :
        arrowLength = max(arrowLength - tipProtruding, 2.0)
    
    lengthPrecision     = 0.01
    # removePatchStroke   = False # optionnaly remove the path that ensures head contact
    recursionLimit      = 16
    
    # Undo and context
    # ----------------
    
    monImage.undo_group_start()
    Gimp.context_push()
    # Gimp.context_set_defaults()
    
    # get active layer
    # ----------------
    
    if createLayer == True :
        
        calqueSource = Gimp.Layer.new(monImage, "Arrows #0", monImage.get_width(), monImage.get_height(), 
                                    monImage.get_base_type() * 2 + 1, 100.0, 28) # 28:normal
        monImage.insert_layer(calqueSource, None, 0)
        
    elif len(drawables) != 1:
        
        Gimp.context_pop()
        monImage.undo_group_end()
        msg = "Procedure '{}' only works with one drawable.".format(procedure.get_name())
        error = GLib.Error.new_literal(Gimp.PlugIn.error_quark(), msg, 0)
        return procedure.new_return_values(Gimp.PDBStatusType.CALLING_ERROR, error)
        
    else:
        
        calqueSource = drawables[0]
            
    # end if
    
    #*********************************************************************************
    
    #***********
    # Main code
    #***********
    
    # accumulatedCalcTime = 0 # debug
    
    userPaths = monImage.get_selected_paths()
    
    if userPaths == [] :
        
        Gimp.context_pop()
        monImage.undo_group_end()
        msg = "Procedure '{}' needs at least one selected path".format(procedure.get_name())
        error = GLib.Error.new_literal(Gimp.PlugIn.error_quark(), msg, 0)
        return procedure.new_return_values(Gimp.PDBStatusType.CALLING_ERROR, error)
    
    
    # work on each selected path successively
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    
    for thisPath in userPaths :
        
        # time1 = time.perf_counter() # debug
        
        # prepare shortening of the stroke and get angles
        # -----------------------------------------------
        
        allStrokes = thisPath.get_strokes()
        thisStroke = allStrokes[-1]
        strokeLength = thisPath.stroke_get_length(thisStroke, lengthPrecision)
        
        # find anchor placement of the head
        axisLength = harpoonFactor * arrowLength
        anchorDist = strokeLength - axisLength
        
        if arrowStyle == "empty" or arrowStyle == "simple" :
            anchorDist -= tipProtruding
            
        if anchorDist <= 0.0 :
            break # path too short
        
        getNewEnd = thisPath.stroke_get_point_at_dist(thisStroke, anchorDist, lengthPrecision) # True, x, y, slope, valid
        anchorX = getNewEnd[1]
        anchorY = getNewEnd[2]
        
        flatPointsList = thisPath.stroke_get_points(thisStroke)[1]
        # print(pointsList) # debug
        
        # convert coords list to points list
        last = len(flatPointsList) / 2 - 1
        i = 1
        pointsList = []
        
        while i < last :
            
            thisPoint = [flatPointsList[2*i], flatPointsList[2*i+1]]
            pointsList.append(thisPoint)
            i += 1
            
        # end while
        
        # list extractions
        newPointsList = pointsList[:-4] # to complete with the new end segment
        lastSegment = pointsList[-4:]
        
        # find length of last segment
        flatLastSegment = [ lastSegment[0][0], lastSegment[0][1] ]  # start with first handle. Déplacer dans segmentLength >
        flatLastSegment.extend( flattenPoints(lastSegment) )
        flatLastSegment.extend( lastSegment[-1] )                   # end with last handle. Déplacer dans segmentLength <
        lastSegmentLength = segmentLength(flatLastSegment, thisPath, lengthPrecision)
        
        shortening = axisLength
        
        # if middle point is too close to the end :
        # ---------------------------------------
        if lastSegmentLength < axisLength and len(pointsList) > 4 : 
            
            # we now consider the second last segment
            newPointsList = pointsList[:-7]
            lastSegment = pointsList[-7:-3]
            
            flatLastSegment = [ lastSegment[0][0], lastSegment[0][1] ]  # start with first handle. Déplacer dans segmentLength >
            flatLastSegment.extend( flattenPoints(lastSegment) )
            flatLastSegment.extend( lastSegment[-1] )                   # end with last handle. Déplacer dans segmentLength <
            lastSegmentLength = segmentLength(flatLastSegment, thisPath, lengthPrecision)
            
            shortening = axisLength - lastSegmentLength
            
        # end if
            
        
        # search for the t parameter of split bezier at anchor point
        # ----------------------------------------------------------
        
        target = [anchorX, anchorY]
        # name change for more clarity
        fullSegment = lastSegment.copy()
        
        # print("full segment:", fullSegment) # debug
        
        # prepare failure iteration
        segmentsCount = 8 # default starting segment division
        segIncrement  = 3 # increment segmentsCount by this value at each new try
        maxTries    = 6
        targetDist  = 99999.0
        whileCount  = 0
        found       = False
        abortThis   = False
        
        # in case of failure (target is too far from found point), iterate with more segments
        while found == False :
            
            recursionCount = 0
            
            # create points list
            
            tInterval = 1.0 / segmentsCount
            initP = [ fullSegment[0] ]      # first point (not used, for list completeness)
            initT = [ 0.0 ]                 # first t
            initD = [ 9999.0 ]              # first dist (not used)
            bestD = 9999.0
            
            i = 1
            
            # walk through all points except first and last
            while i < segmentsCount :
                
                thisT = float(i) * tInterval
                thisP = sliceBezier(fullSegment, thisT)[3]
                thisD = distance( thisP, target )
                initT.append(thisT)
                initP.append(thisP)
                initD.append(thisD)
                
                if thisD < bestD :
                    
                    bestD = thisD
                    bestI = i
                    
                # end if
                
                i += 1 ###
                
            # end while
            
            # lists completion
            initT.append(1.0)
            initP.append(fullSegment[-1]) # not mandatory, for completeness
            initD.append(9999.0)          # not mandatory
            
            # new list of 3 points to send to recursion
            pList = [ initP[bestI-1], initP[bestI], initP[bestI+1] ]
            tList = [ initT[bestI-1], initT[bestI], initT[bestI+1] ]
            
            recursionCount = 0
            t, foundP, found = findBezierPoint(target, fullSegment, tList, pList, bestD, 
                    recursionCount, recursionLimit)
            
            segmentsCount += segIncrement
            whileCount += 1
            
            # print("target dist:", targetDist) # debug
            
            if whileCount > maxTries : # only so many tries
                abortThis = True
                break # go away
            
            # print("target dist:" + str(targetDist)) # debug
            
        # end while found
        
        if abortThis == True :
            continue # interrupt this path's iteration
        
        # finally, we have a close enough t parameter
        getSegment = sliceBezier(fullSegment, t)
        
        
        # complete the points list and angle calculation
        # ----------------------------------------------
        
        # add the first handle back and refactor list for GIMP's coordinates list format
        
        newEndSegment = getSegment[0:4]
        
        newEndSegment.append(getSegment[3]) # last handle must have same coord as the point
        
        # determine the path angle at anchor point
        # ----------------------------------------
        
        endAngle = math.atan( ( getSegment[3][1]- getSegment[2][1] ) / ( getSegment[3][0] - getSegment[2][0] ) )
        
        if getSegment[3][0] - getSegment[2][0] < 0.0 :
            
            endAngle += math.pi
        
        # print("end angle:" + str(endAngle))     # debug
        # time2 = time.perf_counter()             # debug
        # accumulatedCalcTime += (time2 - time1)  # debug
        
        # draw a patch at anchor point to remove visible spacing between head and body
        # ----------------------------------------------------------------------------
        
        if arrowStyle != "empty" :
            
            if arrowStyle == "simple" :
                
                patchLength = arrowLength / 2.0 - strokeWidth
                
            else :       # = "filled"
                
                patchLength = harpoonFactor**2 * strokeWidth
            
            patchEndX   = anchorX + math.cos(endAngle) * patchLength
            patchEndY   = anchorY + math.sin(endAngle) * patchLength
            
            patchPathPoints = [
                        [patchEndX, patchEndY],
                        [patchEndX, patchEndY],
                        [patchEndX, patchEndY]
                        ]
            # end if
        #end if
        
        
        # complete the path
        # -----------------
        
        newPointsList.extend(newEndSegment)
        
        if arrowStyle != "empty" :
            newPointsList.extend(patchPathPoints)
            
        # end if
        
        # print("new end segment:", newEndSegment) # debug
        
        newFlatList = flattenPoints(newPointsList)
        newFlatList.insert(0, newFlatList[0])
        newFlatList.insert(1, newFlatList[2])
        # newFlatList.extend(newFlatList[-2:])
        
        # print(newFlatList) # debug
        
        newPath = Gimp.Path.new(monImage, "body path #1")
        newPath.stroke_new_from_points(0, newFlatList, False)
        
        monImage.insert_path(newPath, None, 0)
        
        # ****************************************************************************
        
        # set context and stroke the body
        # -------------------------------
        
        # Gimp.context_set_foreground(fgColor)
        Gimp.context_set_antialias(True)
        Gimp.context_set_feather(False)
        
        Gimp.context_set_line_width(strokeWidth)
        Gimp.context_set_line_join_style(0) #MITER
        Gimp.context_set_line_cap_style(0)  #BUTT
        Gimp.context_set_stroke_method(0)   #LINE
        Gimp.context_set_line_miter_limit(100.0) # max value accepted by GIMP: 100.0
        
        if arrowHeadOnly == False :
            
            calqueSource.edit_stroke_item(newPath)
        
        # end if
        
        # # clean patch stroke
        # if arrowStyle != "empty" and removePatchStroke == True :
            
            # newPath.remove_stroke(patchStroke) # optional
            
        # # end if
        
        # ****************************************************************************
        
        # construct the arrow head
        # ------------------------
        
        
        tipX = anchorX + math.cos(endAngle) * axisLength
        tipY = anchorY + math.sin(endAngle) * axisLength
        
        wingLength = arrowLength / math.cos( tipAngle / 2.0 )
        
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
        
        # ****************************************************************************
        
        # fill or stroke the arrow head
        # -----------------------------
        
        if arrowStyle == "filled" :
            
            if Gimp.Selection.is_empty(monImage) :
                monImage.select_item(2, arrowPath) # 2: replace
            else :
                monImage.select_item(3, arrowPath) # 3: intersect
                
            if Gimp.Selection.is_empty(monImage) == False :
                calqueSource.edit_fill(0) # 0: FG color
                
            monImage.select_item(2, savedSelection)
            
        else :
            
            calqueSource.edit_stroke_item(arrowPath)
            
        # end if
        
        
        # clean unwanted paths
        # --------------------
        if keepPaths == False :
            
            monImage.remove_path(newPath)
            monImage.remove_path(arrowPath)
            
        # end if
        
    # end for thisPath in userPaths
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    
    
    # crop if new layer
    # -----------------
    
    if createLayer == True :
        
        monImage.select_item(2, calqueSource)
        boundingBox = Gimp.Selection.bounds(monImage)
        # print("bounds : " + str(boundingBox)) # debug
        offsetX = -boundingBox[2] # no idea why negative
        offsetY = -boundingBox[3]
        width = boundingBox[4] - boundingBox[2]
        height = boundingBox[5] - boundingBox[3]
        
        calqueSource.resize(width, height, offsetX, offsetY)
        
    # end if
    
    #*********************************************************************************

    # Finalisations
    # *************

    monImage.select_item(2, savedSelection)
    monImage.remove_channel(savedSelection)
    monImage.set_selected_paths(selectedPaths)
    monImage.set_selected_layers([calqueSource])
    
    Gimp.context_pop()
    monImage.undo_group_end()
    
    
    # print("calc time:", accumulatedCalcTime) # debug
    
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


#*************************************************************************************


def segmentLength(segment, thisPath, lengthPrecision) :

    tempStroke = thisPath.stroke_new_from_points(0, segment, False)
    segmLength = thisPath.stroke_get_length(tempStroke, lengthPrecision)
    thisPath.remove_stroke(tempStroke)
    
    return segmLength


#*************************************************************************************


# distance between two points
def distance(p1, p2) :
    
    dist = math.hypot(p2[1] - p1[1], p2[0] - p1[0])
    
    return dist


#*************************************************************************************


# flatten points list to list of coordinates for GIMP path format
def flattenPoints(pointsList) :
    
    flatList = []
    
    for thisPoint in pointsList :
        
        flatList += thisPoint
        
    # end for
    
    return flatList


#*************************************************************************************


# recursive search for the t parameter of a target point on curve
# ---------------------------------------------------------------
def findBezierPoint(target, fullSegment, tList, pointsList, middlePointDist, 
                    recursionCount, recursionLimit) :
    
    p1, p3, p5 = pointsList
    t1, t3, t5 = tList
    d3 = middlePointDist
    
    t2 = (t1 + t3) / 2.0
    t4 = (t3 + t5) / 2.0
    tlst = [t1, t2, t3, t4, t5]
    
    # create 2 new points
    p2 = sliceBezier(fullSegment, t2)[3]
    p4 = sliceBezier(fullSegment, t4)[3]
    plst = [p1, p2, p3, p4, p5]
    
    # get distances to target
    d2 = distance(p2, target)
    d4 = distance(p4, target)
    dlst = [d2,d3,d4]
    
    # print(plst) # debug
    # print(dlst) # debug
    
    dMin = 99999.0
    
    i = 0
    while i < 3 :
        
        if dlst[i] < dMin :
            dMin = dlst[i]
            besti = i
            
        i += 1
    # end while
    
    # print( "distance:", dMin ) # debug
    
    j = besti + 1 # j is for lists of length 5
    
    # print(j) # debug
    
    # stop condition:
    
    if dMin < 0.2 :
        
        return tlst[j], plst[j], True # found!
        
    elif recursionCount >= recursionLimit :
        
        return tlst[j], plst[j], False # false positive
    # end if
    
    tList = [ tlst[j-1], tlst[j], tlst[j+1] ]
    pointsList = [ plst[j-1], plst[j], plst[j+1] ]
    
    # print("target:", target, "points:", pointsList) # debug
    
    recursionCount += 1
    
    return findBezierPoint(target, fullSegment, tList, pointsList, dMin, 
                    recursionCount, recursionLimit)
    
    
#***************************************************************************************


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

