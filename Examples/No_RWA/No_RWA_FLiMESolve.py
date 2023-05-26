# -*- coding: utf-8 -*-
"""
Created on Sun May 21 23:17:41 2023

@author: Fenton
"""


import matplotlib.pyplot as plt
from qutip import flimesolve,Qobj,basis,destroy,correlation
import numpy as np
# from qutip import *
# from qutip.ui.progressbar import BaseProgressBar
import matplotlib.cm as cm #importing colormaps to plot nicer
import matplotlib


from IPython import get_ipython
# get_ipython().run_line_magic('matplotlib', 'qt')

'''
Modelling on Josepheson junction QUbits, because I see no reason not to
Google says these have transition frequencies in the 1-10 GHz range.

Choosing an intermediate value of 5.
'''
wres = 2*np.pi*280 #THz

'''
For loop used to create the range of powers for laser 2.
The way it's set up now, the Om_2 will be integers that go up to the value of power_range
'''

Tau_array = [2e+5]



detuning_array = [0]
for idz, periods in enumerate(detuning_array):
    print('Working on Spectra number', idz, 'of',len(Tau_array))
    ############## Experimentally adjustable parameters #####################
    #electric field definitions
    
    '''
    In THz so .01 is rather large
    
    Defining the magnitude off of the resonance frequency because 
        the paper I'm trying to reproduce gives coupling in terms of the 
        resonant frequency. Since my dipole moment has magnitude 1, I define
        the coupling constant here, effectively.'
    '''
    E1mag = wres*0.5
   
    '''
    Defining the polarization that will dot with the dipole moment to form the
    Rabi Frequencies
    '''
    E1pol = np.array([0, 1, 0]); 
   
    
    '''
    Total E field
    '''
    E1 = E1mag*E1pol
   
   
    ############## Hamiltonian parameters ###################################
    '''
    Going to define the states for clarity, although I'll be using the "mat" function
        to make any matrix elements
    
    One ground state, one excited state
    '''
    Hdim = 2 # dimension of Hilbert space
    gnd0 = basis(2,0)       #|0>
    gnd1 = basis(2,1)       #|1>
    
    '''
    Defining the function to make matrix operators |i><j|
    '''
    def mat(i,j):
        return(basis(2,i)*basis(2,j).dag())
    

    '''
    Defining the Dipole moment of the QD that will dot with the laser polarization
        to form the Rabi Frequency and Rabi Frequency Tilde
    '''
    dmag = 1
    d = dmag *  np.sqrt(1/2) * np.array([1, -1j, 0]) 
    
    Om1  = np.dot(d,        E1)
    Om1t = np.dot(d,np.conj(E1))
    
   
    wlas = wres#+((-3+idz)*Om1)
   
    T = 2*np.pi/abs(wlas) # period of the Hamiltonian
    Hargs = {'l': (wlas)}                           #Characteristic frequency of the Hamiltonian is half the beating frequency of the Hamiltonian after the RWA. QuTiP needs it in Dictionary form.
    w = Hargs['l']
    
    '''
    Defining the spontaneous emission operators that will link the two states
    Another paper I've looked up seems to say that decay values of ~275 kHz
        are common. I think.
    '''
    Gamma = wres*0.03   #in THz, roughly equivalent to 1 micro eV
    spont_emis = np.sqrt(Gamma) * mat(0,1)           # Spontaneous emission operator   
    

      
        
    '''
    The following tlist definitions are for different parts of the following calulations
    The first is to iterate the dnesity matrix to some time far in the future, and seems to need a lot of steps for some reason
    The second dictates the number of t values evenly distributed over the "limit cycle" that will be averaged over later
    The third is for the tau values that are used to iterate the matrix forward after multiplying by the B operator
    '''
    
    Nt = (2**4)                                       #Number of Points
    time = T                                          #Length of time of tlist defined to be one period of the system
    dt = time/Nt                                      #Time point spacing in tlist
    tlist = np.linspace(0, time-dt, Nt)               #Combining everything to make tlist
     
                                                      #Taulist Definition
    # Ntau =  int((Nt)*2e+4)                                 #50 times the number of points of tlist
    # taume = (Ntau/Nt)*T                               #taulist goes over 50 periods of the system so that 50 periods can be simulated
    # dtau = taume/Ntau                                 #time spacing in taulist - same as tlist!
    # taulist = np.linspace(0, taume, 2)        #Combining everything to make taulist, and I want taulist to end exactly at the beginning/end of a period to make some math easier on my end later
   
    Ntau =  int((Nt)*2e+4)                                 #50 times the number of points of tlist
    taume = (Ntau/Nt)*T                               #taulist goes over 50 periods of the system so that 50 periods can be simulated
    dtau = taume/Ntau                                 #time spacing in taulist - same as tlist!
    taulist = np.linspace(0, taume-dtau, Ntau)        #Combining everything to make taulist, and I want taulist to end exactly at the beginning/end of a period to make some math easier on my end later
   
     
    Ntau2 = (Nt)*5000                                #50 times the number of points of tlist
    taume2 = (Ntau2/Nt)*T                             #taulist goes over 50 periods of the system so that 50 periods can be simulated
    dtau2 = taume2/Ntau2                              #time spacing in taulist - same as tlist!
    taulist2 = np.linspace(0, taume2-dtau2, Ntau2)   
    if idz == 0:

        
        omega_array1 = np.fft.fftfreq(Ntau2,dtau)
        omega_array = np.fft.fftshift(omega_array1)
        
        ZF = np.zeros( (len(Tau_array), len(omega_array1)) )
   
    ################################# Hamiltonian #################################
    '''
    Finally, I'll define the full system Hamiltonian. Due to the manner in which
        QuTiP accepts Hamiltonians, the Hamiltonian must be defined in separate terms
        based on time dependence. Due to that, the Hamiltonian will have three parts.
        One time independent part, one part that rotates forwards in time, and one
        part that rotates backwards in time. For full derivation, look at my "2LS
        Bichromatic Excitation" subtab under my 4/13/21 report
    '''
   
    
    H_atom = (wres/2)*np.array([[-1,0],
                                [ 0,1]])
    
    Hf1  = -(1/2)*np.array([[    0,Om1],
                                [np.conj(Om1t),  0]])
    
    Hb1 = -(1/2)*np.array([[   0,Om1t],
                                [np.conj(Om1),   0]])
    
  
    
    H0 =  Qobj(H_atom)                                  #Time independant Term
    Hf1 =  Qobj(Hf1)                     #Forward Rotating Term
    Hb1 =  Qobj(Hb1)                     #Backward Rotating Term
  
    Htot= [H0,                                        \
        [Hf1,'exp(1j * l * t )'],                    \
        [Hb1, 'exp(-1j * l * t )']]                                        #Full Hamiltonian in string format, a form acceptable to QuTiP
    
   
    
    print('finished setting up the Hamiltonian')

    ############## Calculate the Emission Spectrum ###############################
    '''
    The Hamiltonian and collapse operators have been defined. Now, the first thing
    to do is supply some initial state rho_0
    Doing the ground state cause why not
    '''
    
    rho0 = basis(2,0)
    
    '''
    Next step is to iterate it FAR forward in time, i.e. far greater than any timescale present in the Hamiltonian
    
    Longest timescale in the Hamiltonian is Delta=.02277 Thz -> 5E-11 seconds
    
    Going to just use 1 second as this should be more than long enough. Might need 
    to multiply by the conversion factor as everything so far is in Thz...
    
    jk just gunna multiply the time scale by a big number
    
    It requires a tlist for some reason so I'll just take the last entry for the next stuff
    '''

    
    TimeEvolF1 = flimesolve(
            Htot,
            rho0,
            taulist,
            c_ops_and_rates = [[destroy(2),Gamma]],
            T = T,
            args = Hargs,
            time_sense = 0,
            quicksolve = True,
            options={"normalize_output": False})
    rhossF = TimeEvolF1.states[-1]
    

    
    '''
    Next step is to iterate this steady state rho_s forward in time. I'll choose the times
    to be evenly spread out within T, the time scale of the Hamiltonian
    
    Also going through one time periods of the Hamiltonian so that I can graph the states
    and make sure I'm in the limit cycle
    '''

    
    PeriodStatesF = flimesolve(
            Htot,
            rhossF,
            taulist[-1]+tlist,
            c_ops_and_rates = [[destroy(2),Gamma]],
            T = T,
            args = Hargs,
            time_sense = 0,
            quicksolve = False,
            options={"normalize_output": False})
    

    testg1 = np.zeros((len(tlist), len(taulist2)), dtype='complex_' ) 
    for tdx in range(len(tlist)):
        '''
        Start here tomorrow. You need to write taulist into the _make_solver
        arguments in Correlation, so that the FLiMESolver can construct
        properly. Then, since I'm probably dropping the automatic timer averaging,
        I'll need to use the for loop (for tdx in range(len(tlist)):) to calculate
        all the different g1s and then average them.'
        '''
    
        testg1[tdx] = correlation.correlation_2op_1t(Htot,
                                                      PeriodStatesF.states[tdx],
                                                      # tlist=None,
                                                      taulist = taulist[-1]+tlist[tdx]+taulist2,
                                                      c_ops=[[mat(0,1),Gamma]],
                                                      a_op = destroy(2).dag(),
                                                      b_op = destroy(2),
                                                      solver="fme",
                                                      reverse = True,
                                                      options = {'T':T},
                                                      args = Hargs)[0]
    
    g1avg = np.average(testg1,axis=0)
    specF = np.fft.fft(g1avg,axis=0)
    specF = np.fft.fftshift(specF)/len(g1avg)

    ZF[idz,:] = specF

fig, ax = plt.subplots(1,1)                                                    #Plotting the results!
ax.semilogy( omega_array+(w/(2*np.pi)), ZF[0], color = 'r' )
# ax.semilogy( omega_array+(w/(2*np.pi)), ZM, color = 'b' )
ax.axvline(x=(-1*abs(Om1)/(2*np.pi)), color='k', linestyle = 'dashed')
ax.axvline(x=(0*abs(Om1)/(2*np.pi)), color='g', linestyle = 'solid')
ax.axvline(x=(1*abs(Om1)/(2*np.pi)), color='r', linestyle = 'dashed')
ax.set_xlabel('Detuning [THz]')
ax.set_ylabel("Amplitude") 
ax.set_title(r'Resonant Bichromatic 2LS $\Omega_1$ = 30 $\Omega_2$ = 0' )
ax.legend(['Mollow Triplet From Correlation Function'])


# Plot on a colorplot
fig, ax = plt.subplots(1,1)
limits = [omega_array[0]+(w/(2*np.pi)),\
          omega_array[-1]+(w/(2*np.pi)),\
          detuning_array[0],\
          detuning_array[-1]]
pos = ax.imshow(ZF,cmap=plt.get_cmap(cm.bwr), aspect='auto', interpolation='nearest', origin='lower',
            extent = limits,  norm=matplotlib.colors.LogNorm(), clim = [1e-6,1e-2]) 

fig.colorbar(pos)
ax.set_xlabel('$\omega_{res}-\omega$ [THz]')
ax.set_ylabel("$\u03A9_{2} (\u03BCeV)$") 

 
# fstates = np.array([i.full() for i in TimeEvolF.states])
# # mstates = np.array([i.full() for i in TimeEvolM.states])
# fig, ax = plt.subplots(2,1)                                                    #Plotting the results!
# ax[0].plot(  taulist/T,np.sqrt(fstates[:,1,1]**2), color = 'black')
# # ax[0].plot(  mstates[:,1,1], color = 'blue')
# ax[0].legend(['Floquet'])
# ax[1].legend(['Direct Integration'])
# # ax.plot( (plot_freq_range), Z3_truncd, color = 'green')

