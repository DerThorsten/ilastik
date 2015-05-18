from PyQt4 import uic, QtGui
from PyQt4.QtGui import *
import os
import logging
import sys
import re
import traceback
from PyQt4.QtCore import pyqtSignal

import pgmlink

from ilastik.applets.tracking.base.trackingBaseGui import TrackingBaseGui
from ilastik.utility.exportingOperator import ExportingGui
from ilastik.utility.gui.threadRouter import threadRouted
from ilastik.utility.gui.titledMenu import TitledMenu
from ilastik.utility.ipcProtocol import Protocol
from ilastik.shell.gui.ipcManager import IPCFacade
from ilastik.config import cfg as ilastik_config

from lazyflow.request.request import Request

logger = logging.getLogger(__name__)
traceLogger = logging.getLogger('TRACE.' + __name__)

class StructuredTrackingGui(TrackingBaseGui, ExportingGui):
    
    withMergers = True
    @threadRouted
    def _setMergerLegend(self, labels, selection):   
        for i in range(1,len(labels)+1):
            if i <= selection:
                labels[i-1].setVisible(True)
            else:
                labels[i-1].setVisible(False)
    
    def _loadUiFile(self):
        # Load the ui file (find it in our own directory)
        localDir = os.path.split(__file__)[0]
        self._drawer = uic.loadUi(localDir+"/drawer.ui")
        
        parameters = self.topLevelOperatorView.Parameters.value        
        if 'maxDist' in parameters.keys():
            self._drawer.maxDistBox.setValue(parameters['maxDist'])
        if 'maxObj' in parameters.keys():
            self._drawer.maxObjectsBox.setValue(parameters['maxObj'])
        if 'divThreshold' in parameters.keys():
            self._drawer.divThreshBox.setValue(parameters['divThreshold'])
        if 'avgSize' in parameters.keys():
            self._drawer.avgSizeBox.setValue(parameters['avgSize'][0])
        if 'withTracklets' in parameters.keys():
            self._drawer.trackletsBox.setChecked(parameters['withTracklets'])
        if 'sizeDependent' in parameters.keys():
            self._drawer.sizeDepBox.setChecked(parameters['sizeDependent'])
        if 'divWeight' in parameters.keys():
            self._drawer.divWeightBox.setValue(parameters['divWeight'])
        if 'transWeight' in parameters.keys():
            self._drawer.transWeightBox.setValue(parameters['transWeight'])
        if 'withDivisions' in parameters.keys():
            self._drawer.divisionsBox.setChecked(parameters['withDivisions'])
        if 'withOpticalCorrection' in parameters.keys():
            self._drawer.opticalBox.setChecked(parameters['withOpticalCorrection'])
        if 'withClassifierPrior' in parameters.keys():
            self._drawer.classifierPriorBox.setChecked(parameters['withClassifierPrior'])
        if 'withMergerResolution' in parameters.keys():
            self._drawer.mergerResolutionBox.setChecked(parameters['withMergerResolution'])
        if 'borderAwareWidth' in parameters.keys():
            self._drawer.bordWidthBox.setValue(parameters['borderAwareWidth'])
        if 'cplex_timeout' in parameters.keys():
            self._drawer.timeoutBox.setText(str(parameters['cplex_timeout']))
        if 'appearanceCost' in parameters.keys():
            self._drawer.appearanceBox.setValue(parameters['appearanceCost'])
        if 'disappearanceCost' in parameters.keys():
            self._drawer.disappearanceBox.setValue(parameters['disappearanceCost'])
        
        return self._drawer

    def initAppletDrawerUi(self):
        super(StructuredTrackingGui, self).initAppletDrawerUi()

        self._allowedTimeoutInputRegEx = re.compile('^[0-9]*$')
        self._drawer.timeoutBox.textChanged.connect(self._onTimeoutBoxChanged)

        if not ilastik_config.getboolean("ilastik", "debug"):
            assert self._drawer.trackletsBox.isChecked()
            self._drawer.trackletsBox.hide()
            
            assert not self._drawer.hardPriorBox.isChecked()
            self._drawer.hardPriorBox.hide()

            assert not self._drawer.opticalBox.isChecked()
            self._drawer.opticalBox.hide()

            self._drawer.maxDistBox.hide() # hide the maximal distance box
            self._drawer.label_2.hide() # hie the maximal distance label
            self._drawer.label_5.hide() # hide division threshold label
            self._drawer.divThreshBox.hide()
            self._drawer.label_25.hide() # hide avg. obj size label
            self._drawer.avgSizeBox.hide()
          
        self.mergerLabels = [self._drawer.merg1,
                             self._drawer.merg2,
                             self._drawer.merg3,
                             self._drawer.merg4,
                             self._drawer.merg5,
                             self._drawer.merg6,
                             self._drawer.merg7]
        for i in range(len(self.mergerLabels)):
            self._labelSetStyleSheet(self.mergerLabels[i], self.mergerColors[i+1])
        
        self._onMaxObjectsBoxChanged()
        self._drawer.maxObjectsBox.valueChanged.connect(self._onMaxObjectsBoxChanged)                
        self._drawer.ImportAnnotationsButton.clicked.connect(self._onImportAnnotationsButtonPressed)
        self._drawer.StructuredLearningButton.clicked.connect(self._onRunStructuredLearningButtonPressed)

    @threadRouted
    def _onTimeoutBoxChanged(self, *args):
        inString = str(self._drawer.timeoutBox.text())
        if self._allowedTimeoutInputRegEx.match(inString) is None:
            self._drawer.timeoutBox.setText(inString.decode("utf8").encode("ascii", "replace")[:-1])

    def _setRanges(self, *args):
        super(StructuredTrackingGui, self)._setRanges()
        maxx = self.topLevelOperatorView.LabelImage.meta.shape[1] - 1
        maxy = self.topLevelOperatorView.LabelImage.meta.shape[2] - 1
        maxz = self.topLevelOperatorView.LabelImage.meta.shape[3] - 1
        
        maxBorder = min(maxx, maxy)
        if maxz != 0:
            maxBorder = min(maxBorder, maxz)
        self._drawer.bordWidthBox.setRange(0, maxBorder/2)
        
        
    def _onMaxObjectsBoxChanged(self):
        self._setMergerLegend(self.mergerLabels, self._drawer.maxObjectsBox.value())
        
    def _onImportAnnotationsButtonPressed(self):
        self._annotations = self.mainOperator.Annotations.value
        print "ImportAnnotations PRESSED annotations ",self._annotations

    def _onRunStructuredLearningButtonPressed(self):

        self._onImportAnnotationsButtonPressed()

        print "RunStructuredLearningButton PRESSED crops", self.mainOperator.Crops.value

        print "building consTracker"
        median_obj_size = [0]

        fieldOfView = pgmlink.FieldOfView(float(0),float(0),float(0),float(0),float(self.topLevelOperatorView.LabelImage.meta.shape[0]),float(self.topLevelOperatorView.LabelImage.meta.shape[1]),float(self.topLevelOperatorView.LabelImage.meta.shape[2]),float(self.topLevelOperatorView.LabelImage.meta.shape[3]))
        consTracker = pgmlink.ConsTracking(
            1000000,#maxObj,
            True,#sizeDependent,   # size_dependent_detection_prob
            float(median_obj_size[0]), # median_object_size
            float(30),#maxDist),
            True,#withDivisions,
            float(0.5),#divThreshold),
            "none",  # detection_rf_filename
            fieldOfView,
            "none", # dump traxelstore,
            pgmlink.ConsTrackingSolverType.CplexSolver)

        print "building traxelStore", self.topLevelOperatorView.LabelImage.meta.shape[0], self.topLevelOperatorView.LabelImage.meta.shape[1],self.topLevelOperatorView.LabelImage.meta.shape[2],self.topLevelOperatorView.LabelImage.meta.shape[3]

        traxelStore, empty_frame = self.mainOperator._generate_traxelstore(
            range(0,6),#self.topLevelOperatorView.LabelImage.meta.shape[0]),#time_range
            (0,self.topLevelOperatorView.LabelImage.meta.shape[1]),#x_range
            (0,self.topLevelOperatorView.LabelImage.meta.shape[2]),#y_range
            (0,self.topLevelOperatorView.LabelImage.meta.shape[3]),#z_range,
            (0, 100000),#size_range
            1.0,# x_scale
            1.0,# y_scale
            1.0,# z_scale,
            median_object_size=median_obj_size,
            with_div=True,#withDivisions,
            with_opt_correction=False,#withOpticalCorrection,
            with_classifier_prior=False)#withClassifierPrior)

        if empty_frame:
            raise Exception, 'cannot track frames with 0 objects, abort.'

        print "building Hypotheses Graph"
        hypothesesGraph = consTracker.buildGraph(traxelStore)

        print "building structuredLearningTracker"
        structuredLearningTracker = pgmlink.StructuredLearningTracking(
            hypothesesGraph,
            4,#maxObj,
            True,#sizeDependent,   # size_dependent_detection_prob
            float(median_obj_size[0]), # median_object_size
            float(30),#maxDist),
            True,#withDivisions,
            float(0.5),#divThreshold),
            "none",  # detection_rf_filename
            fieldOfView,
            "none", # dump traxelstore,
            pgmlink.ConsTrackingSolverType.CplexSolver)

        print "update hypothesesGraph: labels ---> adding APPEARANCE/TRANSITION/DISAPPEARANCE nodes"

        for cropKey in self.mainOperator.Annotations.value.keys():
            crop = self.mainOperator.Annotations.value[cropKey]
            print "cropKey, crop",cropKey, crop

            if "labels" in crop.keys():
                labels = crop["labels"]
                for time in labels.keys():
                    print "time, labels", time, labels[time]
                    for label in labels[time].keys():
                        object = labels[time][label]
                        track = object.pop() # This REMOVES an element of a set.
                        object.add(track)
                        print label, track

                        # is this a FIRST, INTERMEDIATE, LAST, SINGLETON(FIRST_LAST) object of a track or FALSE_DETECTION
                        type = self._type(time, track, cropKey)
                        print type



            if "divisions" in crop.keys():
                divisions = crop["divisions"]
                for track in divisions.keys():
                    division = divisions[track]
                    print "track, division, time", track, division, division[1]
                    print division[1],"      : ", track, "--->", division[0][0]
                    print division[1],"      : ", track, "--->", division[0][1]

        # print "EXPORTING CROPS"
        # for key in self.mainOperator.Crops.value.keys():
        #     crop = self.mainOperator.Crops.value[key]
        #     print "PYTHON---->",crop
        #     fieldOfView = pgmlink.FieldOfView(float(crop["time"][0]),float(crop["starts"][0]),float(crop["starts"][1]),float(crop["starts"][2]),float(crop["time"][1]),float(crop["stops"][0]),float(crop["stops"][1]),float(crop["stops"][2]))
        #
        #     print "exporting Crop to C++"
        #     structuredLearningTracker.exportCrop(fieldOfView)

    def _type(self, time, track, cropKey):

        type = None
        if track == -1:
            return "FALSE_DETECTION"
        elif time == 0:
            type = "FIRST"

        labels = self.mainOperator.Annotations.value[cropKey]["labels"]
        crop = self.mainOperator.Crops.value[cropKey]
        lastTime = -1
        #scan preceeding time frames for track
        for t in range(crop["time"][0],time):
            for label in labels[t]:
                if track in labels[t][label]:
                    lastTime = t

        if lastTime == -1:
            type = "FIRST"
        elif lastTime < time-1:
            print "ERROR: Your annotations are not complete. See time frame:", time-1
        elif lastTime == time-1:
            type =  "INTERMEDIATE"
        else:
            print "SHOULD NOT GET HERE!"

        firstTime = -1
        #scan following time frames for track
        for t in range(crop["time"][1],time,-1):
            for label in labels[t]:
                if track in labels[t][label]:
                    firstTime = t

        if firstTime == -1:
            if type == "FIRST":
                return "SINGLETON(FIRST_LAST)"
            else:
                return "LAST"
        elif firstTime > time+1:
            print "ERROR: Your annotations are not complete. See time frame:", time+1
        elif firstTime == time+1:
            if type ==  "INTERMEDIATE":
                return "INTERMEDIATE"
            elif type != None:
                return type,"<-----"
            else:
                print "Something is wrong!"
        else:
            print "Should not get here!"

    def _onTrackButtonPressed( self ):
        if not self.mainOperator.ObjectFeatures.ready():
            self._criticalMessage("You have to compute object features first.")            
            return
        
        def _track():    
            self.applet.busy = True
            self.applet.appletStateUpdateRequested.emit()
            maxDist = self._drawer.maxDistBox.value()
            maxObj = self._drawer.maxObjectsBox.value()        
            divThreshold = self._drawer.divThreshBox.value()
            
            from_t = self._drawer.from_time.value()
            to_t = self._drawer.to_time.value()
            from_x = self._drawer.from_x.value()
            to_x = self._drawer.to_x.value()
            from_y = self._drawer.from_y.value()
            to_y = self._drawer.to_y.value()        
            from_z = self._drawer.from_z.value()
            to_z = self._drawer.to_z.value()        
            from_size = self._drawer.from_size.value()
            to_size = self._drawer.to_size.value()        
            
            self.time_range =  range(from_t, to_t + 1)
            avgSize = [self._drawer.avgSizeBox.value()]

            cplex_timeout = None
            if len(str(self._drawer.timeoutBox.text())):
                cplex_timeout = int(self._drawer.timeoutBox.text())

            withTracklets = self._drawer.trackletsBox.isChecked()
            sizeDependent = self._drawer.sizeDepBox.isChecked()
            hardPrior = self._drawer.hardPriorBox.isChecked()
            classifierPrior = self._drawer.classifierPriorBox.isChecked()
            divWeight = self._drawer.divWeightBox.value()
            transWeight = self._drawer.transWeightBox.value()
            withDivisions = self._drawer.divisionsBox.isChecked()        
            withOpticalCorrection = self._drawer.opticalBox.isChecked()
            withMergerResolution = self._drawer.mergerResolutionBox.isChecked()
            borderAwareWidth = self._drawer.bordWidthBox.value()
            withArmaCoordinates = True
            appearanceCost = self._drawer.appearanceBox.value()
            disappearanceCost = self._drawer.disappearanceBox.value()
    
            ndim=3
            if (to_z - from_z == 0):
                ndim=2
            
            try:
                self.mainOperator.track(
                    time_range = self.time_range,
                    x_range = (from_x, to_x + 1),
                    y_range = (from_y, to_y + 1),
                    z_range = (from_z, to_z + 1),
                    size_range = (from_size, to_size + 1),
                    x_scale = self._drawer.x_scale.value(),
                    y_scale = self._drawer.y_scale.value(),
                    z_scale = self._drawer.z_scale.value(),
                    maxDist=maxDist,         
                    maxObj = maxObj,               
                    divThreshold=divThreshold,
                    avgSize=avgSize,                
                    withTracklets=withTracklets,
                    sizeDependent=sizeDependent,
                    divWeight=divWeight,
                    transWeight=transWeight,
                    withDivisions=withDivisions,
                    withOpticalCorrection=withOpticalCorrection,
                    withClassifierPrior=classifierPrior,
                    ndim=ndim,
                    withMergerResolution=withMergerResolution,
                    borderAwareWidth = borderAwareWidth,
                    withArmaCoordinates = withArmaCoordinates,
                    cplex_timeout = cplex_timeout,
                    appearance_cost = appearanceCost,
                    disappearance_cost = disappearanceCost,
                    graph_building_parameter_changed = True
                    )
            except Exception:           
                ex_type, ex, tb = sys.exc_info()
                traceback.print_tb(tb)            
                self._criticalMessage("Exception(" + str(ex_type) + "): " + str(ex))       
                return                     
        
        def _handle_finished(*args):
            self.applet.busy = False
            self.applet.appletStateUpdateRequested.emit()
            self.applet.progressSignal.emit(100)
            self._drawer.TrackButton.setEnabled(True)
            self._drawer.exportButton.setEnabled(True)
            self._drawer.exportTifButton.setEnabled(True)
            self._setLayerVisible("Objects", False) 
            
        def _handle_failure( exc, exc_info ):
            self.applet.busy = False
            self.applet.appletStateUpdateRequested.emit()
            self.applet.progressSignal.emit(100)
            traceback.print_exception(*exc_info)
            sys.stderr.write("Exception raised during tracking.  See traceback above.\n")
            self._drawer.TrackButton.setEnabled(True)
        
        self.applet.progressSignal.emit(0)
        self.applet.progressSignal.emit(-1)
        req = Request( _track )
        req.notify_failed( _handle_failure )
        req.notify_finished( _handle_finished )
        req.submit()

    def menus(self):
        m = QtGui.QMenu("&Export", self.volumeEditorWidget)
        m.addAction("Export Tracking Information").triggered.connect(self.show_export_dialog)

        return [m]

    def get_raw_shape(self):
        return self.topLevelOperatorView.RawImage.meta.shape

    def get_feature_names(self):
        return self.topLevelOperatorView.ComputedFeatureNames([]).wait()

    def handleEditorRightClick(self, position5d, win_coord):
        debug = ilastik_config.getboolean("ilastik", "debug")

        obj, time = self.get_object(position5d)
        if obj == 0:
            menu = TitledMenu(["Background"])
            if debug:
                menu.addAction("Clear Hilite", IPCFacade().broadcast(Protocol.cmd("clear")))
            menu.exec_(win_coord)
            return

        try:
            color = self.mainOperator.label2color[time][obj]
            tracks = [self.mainOperator.track_id[time][obj]]
            extra = self.mainOperator.extra_track_ids
        except (IndexError, KeyError):
            color = None
            tracks = []
            extra = {}

        if time in extra and obj in extra[time]:
            tracks.extend(extra[time][obj])
        if tracks:
            children, parents = self.mainOperator.track_family(tracks[0])
        else:
            children, parents = None, None

        menu = TitledMenu([
            "Object {} of lineage id {}".format(obj, color),
            "Track ids: " + (", ".join(map(str, set(tracks))) or "None"),
        ])

        if not debug:
            menu.exec_(win_coord)
            return

        if any(IPCFacade().sending):

            obj_sub_menu = menu.addMenu("Hilite Object")
            for mode in Protocol.ValidHiliteModes:
                where = Protocol.simple("and", ilastik_id=obj, time=time)
                cmd = Protocol.cmd(mode, where)
                obj_sub_menu.addAction(mode.capitalize(), IPCFacade().broadcast(cmd))

            sub_menus = [
                ("Tracks", Protocol.simple_in, tracks),
                ("Parents", Protocol.simple_in, parents),
                ("Children", Protocol.simple_in, children)
            ]
            for name, protocol, args in sub_menus:
                if args:
                    sub = menu.addMenu("Hilite {}".format(name))
                    for mode in Protocol.ValidHiliteModes[:-1]:
                        mode = mode.capitalize()
                        where = protocol("track_id*", args)
                        cmd = Protocol.cmd(mode, where)
                        sub.addAction(mode, IPCFacade().broadcast(cmd))
                else:
                    sub = menu.addAction("Hilite {}".format(name))
                    sub.setEnabled(False)

            menu.addAction("Clear Hilite", IPCFacade().broadcast(Protocol.cmd("clear")))
        else:
            menu.addAction("Open IPC Server Window", IPCFacade().show_info)
            menu.addAction("Start IPC Server", IPCFacade().start)

        menu.exec_(win_coord)