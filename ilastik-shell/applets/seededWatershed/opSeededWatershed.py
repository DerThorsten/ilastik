import numpy, vigra, h5py
from lazyflow.operators import OpPixelFeaturesPresmoothed, OpBlockedArrayCache, OpArrayPiper, Op5ToMulti, OpBlockedSparseLabelArray, OpArrayCache, \
                               OpTrainRandomForestBlocked, OpPredictRandomForest, OpSlicedBlockedArrayCache

from lazyflow.graph import Operator, InputSlot, OutputSlot, MultiInputSlot, MultiOutputSlot
from threading import Lock
import pyximport; pyximport.install()
from cylemon.segmentation import GCSegmentor, MSTSegmentorKruskal, MSTSegmentor, PerturbMSTSegmentor
import json

from json import decoder, scanner

from json.scanner import make_scanner
from _json import scanstring as c_scanstring


class OpSegmentor(Operator):

  image     = InputSlot()

  writeSeeds = InputSlot(optional=True)
  deleteSeed = InputSlot(optional=True)

  saveObject = InputSlot(optional=True) 
  loadObject = InputSlot(optional=True) 
  deleteObject = InputSlot(optional=True) 

  update = InputSlot(value = False)
  eraser = InputSlot(value=100)
  algorithm = InputSlot(value="PrioMST")
  parameters = InputSlot(value=dict())
  
  sigma = InputSlot(value=1.6)
  border_indicator = InputSlot(value="hessian_ev_0")
  initial_segmentor = InputSlot(optional = True)

  segmentor = OutputSlot()

  raw = OutputSlot()
  seeds = OutputSlot()
  segmentation = OutputSlot()
  uncertainty = OutputSlot()
  regions = OutputSlot()

  seedNumbers = OutputSlot()
  
  maxUncertainFG = OutputSlot()
  maxUncertainBG = OutputSlot()


  def __init__(self,parent):
    Operator.__init__(self,parent)
    self._dirty   = True
    self._fname = None
    self._algorithm = ""
    self._parameters = {}
    self.seg = None
    self._dirty = True
    self.lock = Lock()
    self.initial_seg = None
    self._dirtySeg = True
    self.initial_segmentor.notifyConnect(self.onInitialSegmentor)
    self.initial_segmentor.notifyMetaChanged(self.onInitialSegmentor)
    self.parameters.notifyMetaChanged(self.onNewParameters)

  def onInitialSegmentor(self, slot):
    if slot.meta.shape is not None:
      print "================= setting initial segmentor"
      seg = slot.value
      if self.initial_seg != seg:
        self.seg = seg
        self._dirtySeg = False
      self.initial_seg = seg

  def onNewParameters(self, slot):
    print "================= setting segmentation to dirty = True"
    self._dirty = True
        
  def updateSeeds(self, oldseg, newseg):
    newseg.seeds.lut[:] = oldseg.seeds.lut[:]

  def setupOutputs(self):  

    self.segmentor.meta.shape = (1,)
    self.segmentor.meta.dtype = object

    self.seedNumbers.meta.shape = (1,)
    self.seedNumbers.meta.dtype = object
    
    self.deleteSeed.meta.shape = (1,)
    self.deleteSeed.meta.dtype = numpy.uint8

    shape = self.raw.meta.shape = self.image.meta.shape
    self.raw.meta.dtype = self.image.meta.dtype

    self.seeds.meta.shape = shape
    self.seeds.meta.dtype = numpy.uint8

    self.segmentation.meta.shape = shape
    self.segmentation.meta.dtype = numpy.uint8
    
    self.uncertainty.meta.shape = shape
    self.uncertainty.meta.dtype = numpy.uint8

    self.regions.meta.shape = shape
    self.regions.meta.dtype = numpy.uint8

    self._eraser = self.eraser.value

    self.writeSeeds.meta.shape = shape
    self.writeSeeds.meta.dtype = numpy.uint8

    self.saveObject.meta.shape = (1,)
    self.saveObject.meta.dtype = object
    
    self.loadObject.meta.shape = (1,)
    self.loadObject.meta.dtype = object
    
    self.deleteObject.meta.shape = (1,)
    self.deleteObject.meta.dtype = object

    print "####################################### segmentor setupOutputs ############################"
    
  def setInSlot(self, slot, key, value):
    print "setInSlot"
    if self.seg is None:
      self.segmentor.value

    print "  ========================= setInSlot"
    if slot == self.writeSeeds:
      print "  =========================== WriteSeeds"
      key = key[1:-1]
      value = numpy.where(value == self._eraser, 255, value[:])

      self.seg.seeds[key] = value
      self._dirty = True
    
    elif slot == self.deleteSeed:
      label = value
      if label != -1:
        print "DELETING SEED", label

        lut = self.seg.seeds.lut[:]
        lut = numpy.where(lut == label, 0, lut)
        lut = numpy.where(lut > label, lut - 1, lut)
        self.seg.seeds.lut[:] = lut
        self._dirty = True

    elif slot == self.saveObject:
      name, seed = value
      print "   --> Saving object %r from seed %r" % (name, seed)
      if self.seg.object_names.has_key(name):
        objNr = self.seg.object_names[name]
      else:
        # find free objNr
        if len(self.seg.object_names.values())> 0:
          objNr = numpy.max(numpy.array(self.seg.object_names.values())) + 1
        else:
          objNr = 1

      #delete old object, if it exists
      lut_objects = self.seg.objects.lut[:]
      lut_objects[:] = numpy.where(lut_objects == objNr, 0, lut_objects)

      #save new object 
      lut_segmentation = self.seg.segmentation.lut[:]
      lut_objects[:] = numpy.where(lut_segmentation == seed, objNr, lut_objects)

      #save object name with objNr
      self.seg.object_names[name] = objNr

      lut_seeds = self.seg.seeds.lut[:]
      print  "nonzero fg seeds shape: ",numpy.where(lut_seeds == seed)[0].shape
  
      # save object seeds
      self.seg.object_seeds_fg[name] = numpy.where(lut_seeds == seed)[0]
      self.seg.object_seeds_bg[name] = numpy.where(lut_seeds == 1)[0] #one is background

    elif slot == self.loadObject:
      name = value
      objNr = self.seg.object_names[name]
      print "   --> Loading object %r from nr %r" % (name, objNr)

      lut_segmentation = self.seg.segmentation.lut[:]
      lut_objects = self.seg.objects.lut[:]
      lut_seeds = self.seg.seeds.lut[:]

      obj_seeds_fg = self.seg.object_seeds_fg[name]
      obj_seeds_bg = self.seg.object_seeds_bg[name]
      
      # clean seeds
      lut_seeds[:] = 0

      # set foreground and background seeds
      lut_seeds[obj_seeds_fg] = 2
      lut_seeds[obj_seeds_bg] = 1

      # set current segmentation
      lut_segmentation[:] = numpy.where( lut_objects == objNr, 2, 1)
    
    elif slot == self.deleteObject:
      name = value
      if self.seg.object_names.has_key(name):
        objNr = self.seg.object_names[name]
        print "   --> Deleting object %r with nr %r" % (name, objNr)

        #delete object from overall segmentation
        lut_objects = self.seg.objects.lut[:]
        lut_objects[:] = numpy.where(lut_objects == objNr, 0, lut_objects)

        del self.seg.object_names[name]
        del self.seg.object_seeds_fg[name]
        del self.seg.object_seeds_bg[name]




  def execute(self, slot, roi, result):
    key = roi.toSlice()[1:-1]
    if slot == self.raw:
      if self.seg is not None:
        res = self.seg.raw[key]
        result[0,:,:,:,0] = res[:]
    elif slot == self.seeds:
      if self.seg is not None:
        res = self.seg.seeds[key]
        result[0,:,:,:,0] = res[:]
    elif slot == self.regions:
      if self.seg is not None:
        res = self.seg.regionVol[key] % 256
        print "........", result.dtype
        result[0,:,:,:,0] = res[:]
    elif slot == self.seedNumbers:
      if self.seg is not None:
        result[0] = numpy.unique(self.seg.seeds.lut)
      else:
        result[0] = [0]
      return result
    elif slot == self.segmentor:
      self.lock.acquire()
      if self._dirtySeg:
        volume = self.image[:].wait()
        border_indicator = self.border_indicator.value
        sigma = self.sigma.value

        if border_indicator == "hessian_ev_0":
          print "Preprocessor: Eigenvalues (sigma = %r)" % (sigma,)
          fvol = volume.astype(numpy.float32)[0,:,:,:,0]
          volume_feat = vigra.filters.hessianOfGaussianEigenvalues(fvol,sigma)[:,:,:,0]
        elif border_indicator == "hessian_ev_0_inv":
          print "Preprocessor: Eigenvalues (inverted, sigma = %r)" % (sigma,)
          fvol = (numpy.max(volume) - volume).astype(numpy.float32)[0,:,:,:,0]
          volume_feat = vigra.filters.hessianOfGaussianEigenvalues(fvol,sigma)[:,:,:,0]
        volume_ma = numpy.max(volume_feat)
        volume_mi = numpy.min(volume_feat)
        volume_feat = (volume_feat - volume_mi) * 255.0 / (volume_ma-volume_mi)
        print "Preprocessor: Watershed..."
        labelVolume = vigra.analysis.watersheds(volume_feat)[0].astype(numpy.int32)
        print "Preprocessor: Construct MSTSegmentor..."
        mst = MSTSegmentor(labelVolume, volume_feat.astype(numpy.float32), edgeWeightFunctor = "minimum")

        mst.raw = volume[0,:,:,:,0]

        if self.seg is not None:# save and restore the seeds
          seeds = self.seg.seeds[:]
          mst.seeds[:] = seeds

        self.seg = mst
        self._dirtySeg = False
      self.lock.release()
      result[0] = self.seg
      return result

    else:    # segmentation or uncertainty is requested

      # get own outputslot
      segmentor = self.segmentor.value

      algorithm = self.algorithm.value

      if algorithm == "PrioMST" and self.seg.__class__ != MSTSegmentor:
        self.seg = MSTSegmentor.fromOtherSegmentor(self.seg)
      if algorithm == "PrioMSTperturb" and self.seg.__class__ != PerturbMSTSegmentor:
        self.seg = PerturbMSTSegmentor.fromOtherSegmentor(self.seg)
      
      self._parameters = self.parameters.value
      
      labelNumbers = numpy.unique(self.seg.seeds.lut)

      if self._dirty:
        labelCount = len(labelNumbers)
        if not self._parameters.has_key("prios"):
          prios = [1.0] * labelCount
          self._parameters["prios"] = prios
        while labelCount > len(self._parameters["prios"]):
            self._parameters["prios"].append(1.0)
        while labelCount < len(self._parameters["prios"]):
            self._parameters["prios"].pop()
        unaries =  numpy.zeros((self.seg.numNodes,labelCount)).astype(numpy.float32)
        print "parameters", self._parameters
        self.seg.run(unaries, **self._parameters)
        self._dirty = False

      if slot == self.segmentation:
        print " ========== getting segmentation"
        res = self.seg.segmentation[key]
        for l in labelNumbers:
          print "Label=%r, count = %r" % ( l, numpy.sum(numpy.where(res == l, 1, 0)))
      if slot == self.uncertainty:
        res = self.seg.uncertainty[key]
      print res.shape, result.shape
      result[0,:,:,:,0] = res[:]
    return result
  
  def propagateDirty(self, slot, roi):
    if slot in [self.image, self.sigma, self.border_indicator]:
      print "  ======================= setting segmentor to dirty"
      self._dirty = True
      self._dirtySeg = True
      self.segmentor.setDirty(slice(0,1,None))
      self.segmentation.setDirty(slice(None,None,None))


  def maxUncertainFG(self):
    ufg = numpy.where(self.seg.segmentation.lut > 1, self.seg.uncertainty.lut, 0)
    index = numpy.argmax(ufg)
    return self.seg.regionCenter[index]

  def maxUncertainBG(self):
    ufg = numpy.where(self.seg.segmentation.lut == 1, self.seg.uncertainty.lut, 0)
    index = numpy.argmax(ufg)
    return self.seg.regionCenter[index]


class OpShapeReader(Operator):
    """
    This operator outputs the shape of its input image, except the number of channels is set to 1.
    """
    Input = InputSlot()
    OutputShape = OutputSlot(stype='shapetuple')
    
    def setupOutputs(self):
        self.OutputShape.meta.shape = (1,)
        self.OutputShape.meta.axistags = 'shapetuple'
        self.OutputShape.meta.dtype = tuple
    
    def execute(self, slot, roi, result):
        # Our 'result' is simply the shape of our input, but with only one channel
        channelIndex = self.Input.meta.axistags.index('c')
        shapeList = list(self.Input.meta.shape)
        shapeList[channelIndex] = 1
        result[0] = tuple(shapeList)


























