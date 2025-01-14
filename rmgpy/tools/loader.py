#!/usr/bin/env python
# -*- coding: utf-8 -*-

###############################################################################
#                                                                             #
# RMG - Reaction Mechanism Generator                                          #
#                                                                             #
# Copyright (c) 2002-2019 Prof. William H. Green (whgreen@mit.edu),           #
# Prof. Richard H. West (r.west@neu.edu) and the RMG Team (rmg_dev@mit.edu)   #
#                                                                             #
# Permission is hereby granted, free of charge, to any person obtaining a     #
# copy of this software and associated documentation files (the 'Software'),  #
# to deal in the Software without restriction, including without limitation   #
# the rights to use, copy, modify, merge, publish, distribute, sublicense,    #
# and/or sell copies of the Software, and to permit persons to whom the       #
# Software is furnished to do so, subject to the following conditions:        #
#                                                                             #
# The above copyright notice and this permission notice shall be included in  #
# all copies or substantial portions of the Software.                         #
#                                                                             #
# THE SOFTWARE IS PROVIDED 'AS IS', WITHOUT WARRANTY OF ANY KIND, EXPRESS OR  #
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,    #
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE #
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER      #
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING     #
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER         #
# DEALINGS IN THE SOFTWARE.                                                   #
#                                                                             #
###############################################################################


"""
This module contains functions for load existing RMG simulations
by reading in files.
"""
import os.path
import warnings
from rmgpy.chemkin import loadChemkinFile
from rmgpy.solver.liquid import LiquidReactor
from rmgpy.solver.mbSampled import MBSampledReactor
from rmgpy.solver.surface import SurfaceReactor
from rmgpy.solver.base import TerminationConversion

def loadRMGJob(inputFile, chemkinFile=None, speciesDict=None, generateImages=True, useJava=False,
               useChemkinNames=False, checkDuplicates=True):

    if useJava:
        # The argument is an RMG-Java input file
        warnings.warn("The RMG-Java input is no longer supported and may be"\
            "removed in version 2.3.", DeprecationWarning)
        rmg = loadRMGJavaJob(inputFile, chemkinFile, speciesDict, generateImages,
                             useChemkinNames=useChemkinNames, checkDuplicates=checkDuplicates)
        
    else:
        # The argument is an RMG-Py input file
        rmg = loadRMGPyJob(inputFile, chemkinFile, speciesDict, generateImages,
                           useChemkinNames=useChemkinNames, checkDuplicates=checkDuplicates)

    return rmg

def loadRMGPyJob(inputFile, chemkinFile=None, speciesDict=None, generateImages=True,
                 useChemkinNames=False, checkDuplicates=True):
    """
    Load the results of an RMG-Py job generated from the given `inputFile`.
    """
    from rmgpy.rmg.main import RMG
    
    # Load the specified RMG input file
    rmg = RMG(inputFile=inputFile)
    rmg.loadInput(inputFile)
    rmg.outputDirectory = os.path.abspath(os.path.dirname(inputFile))
    
    # Load the final Chemkin model generated by RMG
    if not chemkinFile:
        chemkinFile = os.path.join(os.path.dirname(inputFile), 'chemkin', 'chem.inp')
    if not speciesDict:
        speciesDict = os.path.join(os.path.dirname(inputFile), 'chemkin', 'species_dictionary.txt')
    speciesList, reactionList = loadChemkinFile(chemkinFile, speciesDict,
                                                useChemkinNames=useChemkinNames, checkDuplicates=checkDuplicates)
    
    # Created "observed" versions of all reactive species that are not explicitly
    # identified as  "constant" species
    for reactionSystem in rmg.reactionSystems:
        if isinstance(reactionSystem, MBSampledReactor):
            observedspeciesList = []
            for species in speciesList:
                if '_obs' not in species.label and species.reactive:
                    for constantSpecies in reactionSystem.constantSpeciesList:
                        if species.isIsomorphic(constantSpecies):
                            break
                    else:
                        for species2 in speciesList:
                            if species2.label == species.label + '_obs':
                                break
                        else:
                            observedspecies = species.copy(deep=True)
                            observedspecies.label = species.label + '_obs'
                            observedspeciesList.append(observedspecies)

            speciesList.extend(observedspeciesList)

    # Map species in input file to corresponding species in Chemkin file
    speciesDict = {}
    for spec0 in rmg.initialSpecies:
        for species in speciesList:
            if species.isIsomorphic(spec0):
                speciesDict[spec0] = species
                break
            
    # Generate flux pairs for each reaction if needed
    for reaction in reactionList:
        if not reaction.pairs: reaction.generatePairs()
    
    # Replace species in input file with those in Chemkin file
    for reactionSystem in rmg.reactionSystems:
        if isinstance(reactionSystem, LiquidReactor):
            # If there are constant species, map their input file names to
            # corresponding species in Chemkin file
            if reactionSystem.constSPCNames:
                constSpeciesDict = {}
                for spec0 in rmg.initialSpecies:
                    for constSpecLabel in reactionSystem.constSPCNames:
                        if spec0.label == constSpecLabel:
                            constSpeciesDict[constSpecLabel] = speciesDict[spec0].label
                            break
                reactionSystem.constSPCNames = [constSpeciesDict[sname] for sname in reactionSystem.constSPCNames]

            reactionSystem.initialConcentrations = dict([(speciesDict[spec], conc) for spec, conc in reactionSystem.initialConcentrations.iteritems()])
        elif isinstance(reactionSystem, SurfaceReactor):
            reactionSystem.initialGasMoleFractions = dict([(speciesDict[spec], frac) for spec, frac in reactionSystem.initialGasMoleFractions.iteritems()])
            reactionSystem.initialSurfaceCoverages = dict([(speciesDict[spec], frac) for spec, frac in reactionSystem.initialSurfaceCoverages.iteritems()])
        else:
            reactionSystem.initialMoleFractions = dict([(speciesDict[spec], frac) for spec, frac in reactionSystem.initialMoleFractions.iteritems()])



        for t in reactionSystem.termination:
            if isinstance(t, TerminationConversion):
                t.species = speciesDict[t.species]
        if reactionSystem.sensitiveSpecies != ['all']:
            reactionSystem.sensitiveSpecies = [speciesDict[spec] for spec in reactionSystem.sensitiveSpecies]
    
    # Set reaction model to match model loaded from Chemkin file
    rmg.reactionModel.core.species = speciesList
    rmg.reactionModel.core.reactions = reactionList

    # Generate species images
    if generateImages:
        speciesPath = os.path.join(os.path.dirname(inputFile), 'species')
        try:
            os.mkdir(speciesPath)
        except OSError:
            pass
        for species in speciesList:
            path = os.path.join(speciesPath, '{0!s}.png'.format(species))
            if not os.path.exists(path):
                species.molecule[0].draw(str(path))
    
    return rmg


def loadRMGJavaJob(inputFile, chemkinFile=None, speciesDict=None, generateImages=True,
                   useChemkinNames=False, checkDuplicates=True):
    """
    Load the results of an RMG-Java job generated from the given `inputFile`.
    """
    warnings.warn("The RMG-Java input is no longer supported and may be"\
            "removed in version 2.3.", DeprecationWarning)
    from rmgpy.rmg.main import RMG
    from rmgpy.molecule import Molecule
    
    # Load the specified RMG-Java input file
    # This implementation only gets the information needed to generate flux diagrams
    rmg = RMG(inputFile=inputFile)
    rmg.loadRMGJavaInput(inputFile)
    rmg.outputDirectory = os.path.abspath(os.path.dirname(inputFile))
    
    # Load the final Chemkin model generated by RMG-Java
    if not chemkinFile:
        chemkinFile = os.path.join(os.path.dirname(inputFile), 'chemkin', 'chem.inp')
    if not speciesDict:
        speciesDict = os.path.join(os.path.dirname(inputFile), 'RMG_Dictionary.txt')
    speciesList, reactionList = loadChemkinFile(chemkinFile, speciesDict,
                                                useChemkinNames=useChemkinNames, checkDuplicates=checkDuplicates)
    
    # Bath gas species don't appear in RMG-Java species dictionary, so handle
    # those as a special case
    for species in speciesList:
        if species.label == 'Ar':
            species.molecule = [Molecule().fromSMILES('[Ar]')]
        elif species.label == 'Ne':
            species.molecule = [Molecule().fromSMILES('[Ne]')]
        elif species.label == 'He':
            species.molecule = [Molecule().fromSMILES('[He]')]
        elif species.label == 'N2':
            species.molecule = [Molecule().fromSMILES('N#N')]
    
    # Map species in input file to corresponding species in Chemkin file
    speciesDict = {}
    for spec0 in rmg.initialSpecies:
        for species in speciesList:
            if species.isIsomorphic(spec0):
                speciesDict[spec0] = species
                break
            
    # Generate flux pairs for each reaction if needed
    for reaction in reactionList:
        if not reaction.pairs: reaction.generatePairs()

    # Replace species in input file with those in Chemkin file
    for reactionSystem in rmg.reactionSystems:
        reactionSystem.initialMoleFractions = dict([(speciesDict[spec], frac) for spec, frac in reactionSystem.initialMoleFractions.iteritems()])
        for t in reactionSystem.termination:
            if isinstance(t, TerminationConversion):
                if t.species not in speciesDict.values():
                    t.species = speciesDict[t.species]
    
    # Set reaction model to match model loaded from Chemkin file
    rmg.reactionModel.core.species = speciesList
    rmg.reactionModel.core.reactions = reactionList
    
    # RMG-Java doesn't generate species images, so draw them ourselves now
    if generateImages:
        speciesPath = os.path.join(os.path.dirname(inputFile), 'species')
        try:
            os.mkdir(speciesPath)
        except OSError:
            pass
        for species in speciesList:
            path = os.path.join(speciesPath + '/{0!s}.png'.format(species))
            if not os.path.exists(path):
                species.molecule[0].draw(str(path))
    
    return rmg
