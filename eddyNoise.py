import dicom,os, glob, scipy.io, numpy, vtk, sys, datetime, argparse
from clint.textui import colored
from vtk.util import numpy_support
from scipy.ndimage.filters import uniform_filter
from rolling_window import rolling_window



import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

def eddyCurrentCorrection(UOrg, VOrg, WOrg, randNoiseThreshold=1, eddyCurrentThreshold=8, eddyOrder=2, plotBool=1, verbous=0, plotEddyPlane=1):


    USTD = numpy.zeros((UOrg.shape[0],UOrg.shape[1],UOrg.shape[2]))
    VSTD = numpy.zeros(USTD.shape)
    WSTD = numpy.zeros(USTD.shape)
    

    for kIter in range(UOrg.shape[2]):

        USTD[1:(UOrg.shape[0]-1),1:(UOrg.shape[1]-1), kIter] = numpy.std(rolling_window(UOrg[:,:,kIter,:], (3,3,0), toend=False), axis=(4,3,1))
        VSTD[1:(VOrg.shape[0]-1),1:(VOrg.shape[1]-1), kIter] = numpy.std(rolling_window(VOrg[:,:,kIter,:], (3,3,0), toend=False), axis=(4,3,1))
        WSTD[1:(WOrg.shape[0]-1),1:(WOrg.shape[1]-1), kIter] = numpy.std(rolling_window(WOrg[:,:,kIter,:], (3,3,0), toend=False), axis=(4,3,1))

    
    if verbous:    
        print("Ustd Max: ")
        print(USTD.max())
        print("Vstd Max: ")
        print(VSTD.max())
        print("Wstd Max: ")
        print(WSTD.max())

        print("Ustd Min: ")
        print(USTD.min())
        print("Vstd Min: ")
        print(VSTD.min())
        print("Wstd Min: ")
        print(WSTD.min())

        print("USTD size: ")
        print(USTD.shape)


    

    staticTissueU = UOrg[:,:,:,-1].copy()
    staticTissueV = VOrg[:,:,:,-1].copy()
    staticTissueW = WOrg[:,:,:,-1].copy()

    staticTissueU[(USTD > (eddyCurrentThreshold*USTD.max()/100)) & (VSTD > (eddyCurrentThreshold*VSTD.max()/100) ) & (WSTD > (eddyCurrentThreshold*WSTD.max()/100))] = 0
    staticTissueV[(USTD > (eddyCurrentThreshold*USTD.max()/100)) & (VSTD > (eddyCurrentThreshold*VSTD.max()/100) ) & (WSTD > (eddyCurrentThreshold*WSTD.max()/100))] = 0
    staticTissueW[(USTD > (eddyCurrentThreshold*USTD.max()/100)) & (VSTD > (eddyCurrentThreshold*VSTD.max()/100) ) & (WSTD > (eddyCurrentThreshold*WSTD.max()/100))] = 0

    print(staticTissueU.shape)
    
    if plotBool:
        i = 20

        vmax = numpy.max([UOrg[:,:,i,1].max(), staticTissueU[:,:,i].max()])
        vmin = numpy.min([UOrg[:,:,i,1].min(), staticTissueU[:,:,i].min()])
        vmax = numpy.max([vmax, -vmin])
        vmin = -vmax
    
        #for i in range(1,3):
        # plot with various axes scales
        plt.figure(i)

       
        plt.subplot(121)
        plt.imshow(UOrg[:,:,i,1], vmin=vmin, vmax=vmax, cmap='seismic')
        plt.title('Org data')


           
        plt.subplot(122)
        plt.imshow(staticTissueU[:,:,i], vmin=vmin, vmax=vmax, cmap='seismic')
        plt.title('static tissue')

        plt.show()
            

    del USTD, VSTD, WSTD

    
    flowCorrected = numpy.zeros([UOrg.shape[0], UOrg.shape[1], UOrg.shape[2], 3, UOrg.shape[3]])
   
       
    xInit = numpy.linspace(0, UOrg.shape[0], UOrg.shape[0])
    yInit = numpy.linspace(0, UOrg.shape[1], UOrg.shape[1])
    
    X, Y = numpy.meshgrid(xInit, yInit, sparse=False, indexing='ij')
    
    
    X2=X*X
    Y2=Y*Y
    XY=X*Y
    
    
    plainU = numpy.zeros([UOrg.shape[0], UOrg.shape[1], UOrg.shape[2]])
    plainV = numpy.zeros([UOrg.shape[0], UOrg.shape[1], UOrg.shape[2]])
    plainW = numpy.zeros([UOrg.shape[0], UOrg.shape[1], UOrg.shape[2]])
    
    if eddyOrder == 1:
        # best-fit linear plane
        for iIter in range(UOrg.shape[2]):
            
                BUInd = staticTissueU[:,:,iIter].copy()
                BVInd = staticTissueV[:,:,iIter].copy()
                BWInd = staticTissueW[:,:,iIter].copy()

                notZeroIndU = numpy.nonzero(BUInd)
                notZeroIndV = numpy.nonzero(BVInd)
                notZeroIndW = numpy.nonZero(BWInd)

                BU = BUInd[notZeroIndU].ravel()
                BV = BVInd[notZeroIndV].ravel()
                BW = BWInd[notZeroIndW].ravel()
                
                DU = numpy.c_[X[notZeroIndU].ravel(), Y[notZeroIndU].ravel(), numpy.ones(len(X[notZeroIndU].ravel()))]
                DV = numpy.c_[X[notZeroIndV].ravel(), Y[notZeroIndV].ravel(), numpy.ones(len(X[notZeroIndV].ravel()))]
                DW = numpy.c_[X[notZeroIndV].ravel(), Y[notZeroIndV].ravel(), numpy.ones(len(X[notZeroIndV].ravel()))]
            
                CU,_,_,_ = scipy.linalg.lstsq(DU, BU)    # coefficients
                CV,_,_,_ = scipy.linalg.lstsq(DV, BV)    # coefficients
                CW,_,_,_ = scipy.linalg.lstsq(DW, BW)
        
                # evaluate it on grid
                plainU[:,:,iIter] = CU[0]*X + CU[1]*Y + CU[2]
                plainV[:,:,iIter] = CV[0]*X + CV[1]*Y + CV[2]
                plainW[:,:,iIter] = CW[0]*X + CW[1]*Y + CW[2]


    elif eddyOrder == 2:
        # best-fit quadratic curve
        
        for iIter in range(plainU.shape[2]):

            BUInd = staticTissueU[:,:,iIter].copy()
            BVInd = staticTissueV[:,:,iIter].copy()
            BWInd = staticTissueW[:,:,iIter].copy()

            notZeroIndU = numpy.nonzero(BUInd)
            notZeroIndV = numpy.nonzero(BVInd)
            notZeroIndW = numpy.nonzero(BWInd)

            BU = BUInd[notZeroIndU].ravel()
            BV = BVInd[notZeroIndV].ravel()
            BW = BWInd[notZeroIndW].ravel()
                
            DU = numpy.c_[X[notZeroIndU].ravel(), Y[notZeroIndU].ravel(), XY[notZeroIndU].ravel(), X2[notZeroIndU].ravel() , Y2[notZeroIndU].ravel() , numpy.ones(len(X[notZeroIndU].ravel()))]
            DV = numpy.c_[X[notZeroIndV].ravel(), Y[notZeroIndV].ravel(), XY[notZeroIndV].ravel(), X2[notZeroIndV].ravel() , Y2[notZeroIndV].ravel() , numpy.ones(len(X[notZeroIndV].ravel()))]
            DW = numpy.c_[X[notZeroIndW].ravel(), Y[notZeroIndW].ravel(), XY[notZeroIndW].ravel(), X2[notZeroIndW].ravel() , Y2[notZeroIndW].ravel() , numpy.ones(len(X[notZeroIndW].ravel()))]

            CU,_,_,_ = scipy.linalg.lstsq(DU, BU)    # coefficients
            CV,_,_,_ = scipy.linalg.lstsq(DV, BV)    # coefficients
            CW,_,_,_ = scipy.linalg.lstsq(DW, BW)
        
            # evaluate it on grid
            plainU[:,:,iIter] = CU[0]*X + CU[1]*Y + CU[2]*XY + CU[3]*X2 + CU[4]*Y2 + CU[5]
            plainV[:,:,iIter] = CV[0]*X + CV[1]*Y + CV[2]*XY + CV[3]*X2 + CV[4]*Y2 + CV[5]
            plainW[:,:,iIter] = CW[0]*X + CW[1]*Y + CW[2]*XY + CW[3]*X2 + CW[4]*Y2 + CW[5]
            
    
    
    if plotEddyPlane:
        plt.figure(2)
        Axes3D.plot_surface(X, Y,  plainU[:,:,20])  
        plt.show()  
   


    for k in range(UOrg.shape[3]):
        
        flowCorrected[:, :, :,0, k] = UOrg[:,:,:,k] - plainU
        flowCorrected[:, :, :,1, k] = VOrg[:,:,:,k] - plainV
        flowCorrected[:, :, :,2, k] = WOrg[:,:,:,k] - plainW
    
    
    return flowCorrected

def randNoise(UOrg, VOrg, WOrg, randThre=25, plotBool=1):

    USTD = numpy.zeros((UOrg.shape[0],UOrg.shape[1],UOrg.shape[2]))
    VSTD = numpy.zeros(USTD.shape)
    WSTD = numpy.zeros(USTD.shape)
    

    for kIter in range(UOrg.shape[2]):

        USTD[1:(UOrg.shape[0]-1),1:(UOrg.shape[1]-1), kIter] = numpy.std(rolling_window(UOrg[:,:,kIter,:], (3,3,0), toend=False), axis=(4,3,1))
        VSTD[1:(VOrg.shape[0]-1),1:(VOrg.shape[1]-1), kIter] = numpy.std(rolling_window(VOrg[:,:,kIter,:], (3,3,0), toend=False), axis=(4,3,1))
        WSTD[1:(WOrg.shape[0]-1),1:(WOrg.shape[1]-1), kIter] = numpy.std(rolling_window(WOrg[:,:,kIter,:], (3,3,0), toend=False), axis=(4,3,1))
            
    
    flowCorrected = numpy.zeros([UOrg.shape[0], UOrg.shape[1], UOrg.shape[2],3,UOrg.shape[3]])


    UOrg[(USTD > (randThre*USTD.max()/100)) & (VSTD > (randThre*VSTD.max()/100) ) & (WSTD > (randThre*WSTD.max()/100))] = 0
    VOrg[(USTD > (randThre*USTD.max()/100)) & (VSTD > (randThre*VSTD.max()/100) ) & (WSTD > (randThre*WSTD.max()/100))] = 0
    WOrg[(USTD > (randThre*USTD.max()/100)) & (VSTD > (randThre*VSTD.max()/100) ) & (WSTD > (randThre*WSTD.max()/100))] = 0



    flowCorrected[:,:,:,0] = UOrg
    flowCorrected[:,:,:,1] = VOrg
    flowCorrected[:,:,:,2] = WOrg

    
    if plotBool:
        vmax = numpy.max([UOrg[:,:,20,1].max(), VOrg[:,:,20,1].max(), WOrg[:,:,20,1].max()])
        vmin = numpy.min([UOrg[:,:,20,1].min(), VOrg[:,:,20,1].min(), WOrg[:,:,20,1].min()])
        vmax = numpy.max([vmax, -vmin])
        vmin = -vmax

        # plot with various axes scales
        plt.figure(1)

       
        plt.subplot(131)
        plt.imshow(UOrg[:,:,20,1], vmin=vmin, vmax=vmax, cmap='seismic')
        plt.title('U Org')


       
        plt.subplot(132)
        plt.imshow(VOrg[:,:,20, 1], vmin=vmin, vmax=vmax, cmap='seismic')
        plt.title('V Org')

        plt.subplot(133)
        plt.imshow(WOrg[:,:,20, 1], vmin=vmin, vmax=vmax, cmap='seismic')
        plt.title('W Org')

        plt.show()
    

    return flowCorrected





