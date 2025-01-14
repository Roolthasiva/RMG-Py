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

from .graph cimport Vertex, Edge, Graph
from .atomtype cimport AtomType
cimport rmgpy.molecule.group as gr
from .element cimport Element
cimport rmgpy.constants as constants
cimport numpy

################################################################################
cdef dict bond_orders 

cdef class Atom(Vertex):

    cdef public Element element
    cdef public short radicalElectrons
    cdef public short charge
    cdef public str label
    cdef public AtomType atomType
    cdef public numpy.ndarray coords
    cdef public short lonePairs
    cdef public int id
    cdef public dict props
    
    cpdef bint equivalent(self, Vertex other, bint strict=?) except -2

    cpdef bint isSpecificCaseOf(self, Vertex other) except -2

    cpdef Vertex copy(self)

    cpdef bint isHydrogen(self)

    cpdef bint isNonHydrogen(self)

    cpdef bint isCarbon(self)

    cpdef bint isOxygen(self)

    cpdef bint isFluorine(self)

    cpdef bint isSilicon(self)

    cpdef bint isSulfur(self)

    cpdef bint isChlorine(self)

    cpdef bint isIodine(self)

    cpdef bint isNOS(self)
    
    cpdef bint isSurfaceSite(self)
    
    cpdef incrementRadical(self)

    cpdef decrementRadical(self)
    
    cpdef setLonePairs(self, int lonePairs)
    
    cpdef incrementLonePairs(self)
    
    cpdef decrementLonePairs(self)
    
    cpdef updateCharge(self)

    cpdef getBondOrdersForAtom(self)
    
################################################################################
    
cdef class Bond(Edge):

    cdef public float order

    cpdef bint equivalent(self, Edge other) except -2

    cpdef bint isSpecificCaseOf(self, Edge other) except -2

    cpdef str getOrderStr(self)
    
    cpdef setOrderStr(self, str newOrder)
    
    cpdef float getOrderNum(self)
    
    cpdef setOrderNum(self, float newOrder)

    cpdef Edge copy(self)
    
    cpdef bint isOrder(self, float otherOrder)

    cpdef bint isVanDerWaals(self) except -2

    cpdef bint isSingle(self) except -2

    cpdef bint isDouble(self) except -2

    cpdef bint isTriple(self) except -2
    
    cpdef bint isQuadruple(self) except -2
    
    cpdef bint isBenzene(self) except -2

    cpdef incrementOrder(self)

    cpdef decrementOrder(self)

    cpdef str get_bond_string(self)

################################################################################

cdef class Molecule(Graph):

    cdef public bint implicitHydrogens
    cdef public float symmetryNumber
    cdef public int multiplicity
    cdef public bint reactive
    cdef public object rdMol
    cdef public int rdMolConfId
    cdef public dict props
    cdef str _fingerprint
    cdef str _inchi
    cdef str _smiles

    cpdef addAtom(self, Atom atom)

    cpdef addBond(self, Bond bond)

    cpdef dict getBonds(self, Atom atom)

    cpdef Bond getBond(self, Atom atom1, Atom atom2)

    cpdef bint hasAtom(self, Atom atom)

    cpdef bint hasBond(self, Atom atom1, Atom atom2)

    cpdef bint containsSurfaceSite(self)
    
    cpdef bint isSurfaceSite(self)

    cpdef removeAtom(self, Atom atom)

    cpdef removeBond(self, Bond bond)

    cpdef removeVanDerWaalsBonds(self)

    cpdef sortAtoms(self)
    
    cpdef str getFormula(self)

    cpdef short getRadicalCount(self)

    cpdef short getSingletCarbeneCount(self)

    cpdef double getMolecularWeight(self)

    cpdef int getNumAtoms(self, str element=?)

    cpdef Graph copy(self, bint deep=?)

    cpdef deleteHydrogens(self)

    cpdef clearLabeledAtoms(self)

    cpdef bint containsLabeledAtom(self, str label) except -2

    cpdef list getLabeledAtom(self, str label)

    cpdef dict getLabeledAtoms(self)

    cpdef dict get_element_count(self)

    cpdef bint isIsomorphic(self, Graph other, dict initialMap=?, bint generateInitialMap=?, bint saveOrder=?, bint strict=?) except -2

    cpdef list findIsomorphism(self, Graph other, dict initialMap=?, bint saveOrder=?, bint strict=?)

    cpdef bint isSubgraphIsomorphic(self, Graph other, dict initialMap=?, bint generateInitialMap=?, bint saveOrder=?) except -2

    cpdef list findSubgraphIsomorphisms(self, Graph other, dict initialMap=?, bint saveOrder=?)

    cpdef bint isAtomInCycle(self, Atom atom) except -2

    cpdef bint isBondInCycle(self, Bond bond) except -2

    cpdef draw(self, str path)

    cpdef fromInChI(self, str inchistr, backend=?)

    cpdef fromSMILES(self, str smilesstr, backend=?)

    cpdef fromAdjacencyList(self, str adjlist, bint saturateH=?)

    cpdef fromXYZ(self, numpy.ndarray atomicNums, numpy.ndarray coordinates)
    
    cpdef str toInChI(self)

    cpdef str toAugmentedInChI(self)

    cpdef str toInChIKey(self)

    cpdef str toAugmentedInChIKey(self)

    cpdef str toSMILES(self)

    cpdef toAdjacencyList(self, str label=?, bint removeH=?, bint removeLonePairs=?, bint oldStyle=?)

    cpdef bint isLinear(self) except -2

    cpdef bint isHeterocyclic(self) except -2

    cpdef int countInternalRotors(self) except -2

    cpdef double calculateCp0(self) except -1

    cpdef double calculateCpInf(self) except -1
    
    cpdef updateAtomTypes(self, bint logSpecies=?, bint raiseException=?)
    
    cpdef bint isRadical(self) except -2

    cpdef bint has_lone_pairs(self) except -2

    cpdef bint isArylRadical(self, list aromaticRings=?) except -2

    cpdef float calculateSymmetryNumber(self) except -1

    cpdef list generate_resonance_structures(self, bint keep_isomorphic=?, bint filter_structures=?)

    cpdef identifyRingMembership(self)

    cpdef tuple getAromaticRings(self, list rings=?)

    cpdef list getDeterministicSmallestSetOfSmallestRings(self)

    cpdef kekulize(self)

    cpdef assignAtomIDs(self)

    cpdef bint atomIDValid(self)

    cpdef bint isIdentical(self, Molecule other, bint strict=?) except -2

    cpdef dict enumerate_bonds(self)

cdef atom_id_counter
