from PyQt4.QtGui import *
from PyQt4 import uic

import os

from ilastik.applets.layerViewer import LayerViewerGui
from volumina.widgets.thresholdingWidget import ThresholdingWidget

import logging
logger = logging.getLogger(__name__)
traceLogger = logging.getLogger('TRACE.' + __name__)
from lazyflow.tracer import Tracer

from ilastik.utility import bind

class ThresholdMaskingGui(LayerViewerGui):
    """
    """
    
    ###########################################
    ### AppletGuiInterface Concrete Methods ###
    ###########################################
    
    def appletDrawers(self):
        return [ ("Threshold Mask Viewer", self.getAppletDrawerUi() ) ]

    # (Other methods already provided by our base class)

    ###########################################
    ###########################################
    
    def __init__(self, toplevelOperator):
        """
        """
        with Tracer(traceLogger):
            self.toplevelOperator = toplevelOperator
            super(ThresholdMaskingGui, self).__init__([toplevelOperator.InputImage, toplevelOperator.Output, toplevelOperator.InvertedOutput])
            self.handleThresholdGuiValuesChanged(0, 255)
            
    def initAppletDrawerUi(self):
        with Tracer(traceLogger):
            # Load the ui file (find it in our own directory)
            localDir = os.path.split(__file__)[0]
            self._drawer = uic.loadUi(localDir+"/drawer.ui")
            
            layout = QVBoxLayout( self )
            layout.setSpacing(0)
            self._drawer.setLayout( layout )
    
            thresholdWidget = ThresholdingWidget(self)
            thresholdWidget.valueChanged.connect( self.handleThresholdGuiValuesChanged )
            layout.addWidget( thresholdWidget )
            
            def updateDrawerFromOperator():
                minValue, maxValue = (0,255)

                if self.toplevelOperator.MinValue.ready():
                    minValue = self.toplevelOperator.MinValue.value
                if self.toplevelOperator.MaxValue.ready():
                    maxValue = self.toplevelOperator.MaxValue.value

                thresholdWidget.setValue(minValue, maxValue)                
                
            self.toplevelOperator.MinValue.notifyDirty( bind(updateDrawerFromOperator) )
            self.toplevelOperator.MaxValue.notifyDirty( bind(updateDrawerFromOperator) )
                
    def handleThresholdGuiValuesChanged(self, minVal, maxVal):
        with Tracer(traceLogger):
            self.toplevelOperator.MinValue.setValue(minVal)
            self.toplevelOperator.MaxValue.setValue(maxVal)
    
    def getAppletDrawerUi(self):
        return self._drawer
    
    def setupLayers(self, currentImageIndex):
        with Tracer(traceLogger):
            layers = []
    
            # Show the thresholded data
            outputImageSlot = self.toplevelOperator.Output[ currentImageIndex ]
            if outputImageSlot.ready():
                outputLayer = self.createStandardLayerFromSlot( outputImageSlot )
                outputLayer.name = "min <= x <= max"
                outputLayer.visible = True
                outputLayer.opacity = 0.75
                layers.append(outputLayer)
            
            # Show the  data
            invertedOutputSlot = self.toplevelOperator.InvertedOutput[ currentImageIndex ]
            if invertedOutputSlot.ready():
                invertedLayer = self.createStandardLayerFromSlot( invertedOutputSlot )
                invertedLayer.name = "(x < min) U (x > max)"
                invertedLayer.visible = True
                invertedLayer.opacity = 0.25
                layers.append(invertedLayer)
            
            # Show the raw input data
            inputImageSlot = self.toplevelOperator.InputImage[ currentImageIndex ]
            if inputImageSlot.ready():
                inputLayer = self.createStandardLayerFromSlot( inputImageSlot )
                inputLayer.name = "Raw Input"
                inputLayer.visible = True
                inputLayer.opacity = 1.0
                layers.append(inputLayer)
    
            return layers














