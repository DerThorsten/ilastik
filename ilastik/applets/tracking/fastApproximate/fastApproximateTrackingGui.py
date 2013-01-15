from PyQt4 import uic
import os
import logging
from ilastik.applets.tracking.base.trackingGuiBase import TrackingGuiBase

logger = logging.getLogger(__name__)
traceLogger = logging.getLogger('TRACE.' + __name__)

class FastApproximateTrackingGui( TrackingGuiBase ):

    def _loadUiFile(self):
        # Load the ui file (find it in our own directory)
        localDir = os.path.split(__file__)[0]
        self._drawer = uic.loadUi(localDir+"/drawer.ui")
        
        return self._drawer

    def _onTrackButtonPressed( self ):
        divDist = self._drawer.divDistBox.value()
        movDist = self._drawer.movDistBox.value()        
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
        
        distanceFeatures = []
#        if self._drawer.comCheckBox.isChecked():
#            distanceFeatures.append("com")
#        if self._drawer.volCheckBox.isChecked():
#            distanceFeatures.append("count")
                
        if len(distanceFeatures) == 0:
#            self._drawer.comCheckBox.setChecked(True)
            distanceFeatures.append("com")
            
        splitterHandling = self._drawer.splitterHandlingBox.isChecked()
        
        mergerHandling = False
#        mergerHandling = self._drawer.mergerHandlingBox.isChecked()
        
        self.time_range =  range(from_t, to_t + 1)
        
        self.mainOperator.track(
            time_range = self.time_range,
            x_range = (from_x, to_x + 1),
            y_range = (from_y, to_y + 1),
            z_range = (from_z, to_z + 1),
            size_range = (from_size, to_size + 1),
            x_scale = self._drawer.x_scale.value(),
            y_scale = self._drawer.y_scale.value(),
            z_scale = self._drawer.z_scale.value(),
            divDist=divDist,
            movDist=movDist,
            distanceFeatures=distanceFeatures,
            divThreshold=divThreshold,
            splitterHandling=splitterHandling,
            mergerHandling=mergerHandling
            )
        
        self._drawer.exportButton.setEnabled(True)
        self._drawer.exportTifButton.setEnabled(True)
#        self._drawer.lineageTreeButton.setEnabled(True)
                
        self._setLayerVisible("Objects", False)
        