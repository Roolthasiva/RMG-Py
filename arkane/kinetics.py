#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Arkane kinetics module
"""

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

import os.path
import numpy
import string
import logging

from rmgpy.kinetics.arrhenius import Arrhenius, ArrheniusEP, PDepArrhenius, MultiArrhenius, MultiPDepArrhenius
from rmgpy.kinetics.chebyshev import Chebyshev
from rmgpy.kinetics.falloff import ThirdBody, Lindemann, Troe
from rmgpy.kinetics.kineticsdata import KineticsData, PDepKineticsData
from rmgpy.kinetics.tunneling import Wigner, Eckart
import rmgpy.quantity as quantity
from rmgpy.molecule.draw import MoleculeDrawer, createNewSurface
from rmgpy.exceptions import SpeciesError

from arkane.sensitivity import KineticsSensitivity as sa
from arkane.output import prettify
from arkane.common import ArkaneSpecies


################################################################################


class KineticsJob(object):
    """
    A representation of an Arkane kinetics job. This job is used to compute
    and save the high-pressure-limit kinetics information for a single reaction.

    `usedTST` - a boolean representing if TST was used to calculate the kinetics
                if kinetics is already given in the input, then it is False.
    """

    def __init__(self, reaction,
                 Tmin=None,
                 Tmax=None,
                 Tlist=None,
                 Tcount=0,
                 sensitivity_conditions=None):
        self.usedTST = False
        self.Tmin = Tmin if Tmin is not None else (298, 'K')
        self.Tmax = Tmax if Tmax is not None else (2500, 'K')
        self.Tcount = Tcount if Tcount > 3 else 50

        if Tlist is not None:
            self.Tlist = Tlist
            self.Tmin = (min(self.Tlist.value_si), 'K')
            self.Tmax = (max(self.Tlist.value_si), 'K')
            self.Tcount = len(self.Tlist.value_si)
        else:
            self.Tlist = (1 / numpy.linspace(1 / self.Tmax.value_si,
                                            1 / self.Tmin.value_si,
                                            self.Tcount), 'K')

        self.reaction = reaction
        self.kunits = None

        if sensitivity_conditions is not None:
            self.sensitivity_conditions = [quantity.Quantity(condition) for condition in sensitivity_conditions]
        else:
            self.sensitivity_conditions = None

        self.arkane_species = ArkaneSpecies(species=self.reaction.transitionState)

    @property
    def Tmin(self):
        """The minimum temperature at which the computed k(T) values are valid, or ``None`` if not defined."""
        return self._Tmin

    @Tmin.setter
    def Tmin(self, value):
        self._Tmin = quantity.Temperature(value)

    @property
    def Tmax(self):
        """The maximum temperature at which the computed k(T) values are valid, or ``None`` if not defined."""
        return self._Tmax

    @Tmax.setter
    def Tmax(self, value):
        self._Tmax = quantity.Temperature(value)

    @property
    def Tlist(self):
        """The temperatures at which the k(T) values are computed."""
        return self._Tlist

    @Tlist.setter
    def Tlist(self, value):
        self._Tlist = quantity.Temperature(value)

    def execute(self, output_directory=None, plot=True):
        """
        Execute the kinetics job, saving the results within
        the `output_directory`.

        If `plot` is True, then plots of the raw and fitted values for the kinetics
        will be saved.
        """
        self.generateKinetics()
        if output_directory is not None:
            try:
                self.write_output(output_directory)
            except Exception as e:
                logging.warning("Could not write kinetics output file due to error: "
                                "{0} in reaction {1}".format(e, self.reaction.label))
            try:
                self.write_chemkin(output_directory)
            except Exception as e:
                logging.warning("Could not write kinetics chemkin output due to error: "
                                "{0} in reaction {1}".format(e, self.reaction.label))
            if plot:
                try:
                    self.plot(output_directory)
                except Exception as e:
                    logging.warning("Could not plot kinetics due to error: "
                                    "{0} in reaction {1}".format(e, self.reaction.label))
                try:
                    self.draw(output_directory)
                except:
                    logging.warning("Could not draw reaction {1} due to error: {0}".format(e, self.reaction.label))
            if self.sensitivity_conditions is not None:
                logging.info('\n\nRunning sensitivity analysis...')
                sa(self, output_directory)
        logging.debug('Finished kinetics job for reaction {0}.'.format(self.reaction))
        logging.debug(repr(self.reaction))

    def generateKinetics(self):
        """
        Generate the kinetics data for the reaction and fit it to a modified Arrhenius model.
        """

        if isinstance(self.reaction.kinetics, Arrhenius):
            return None
        self.usedTST = True
        kineticsClass = 'Arrhenius'

        tunneling = self.reaction.transitionState.tunneling
        if isinstance(tunneling, Wigner) and tunneling.frequency is None:
            tunneling.frequency = (self.reaction.transitionState.frequency.value_si, "cm^-1")
        elif isinstance(tunneling, Eckart) and tunneling.frequency is None:
            tunneling.frequency = (self.reaction.transitionState.frequency.value_si, "cm^-1")
            tunneling.E0_reac = (sum([reactant.conformer.E0.value_si
                                      for reactant in self.reaction.reactants]) * 0.001, "kJ/mol")
            tunneling.E0_TS = (self.reaction.transitionState.conformer.E0.value_si * 0.001, "kJ/mol")
            tunneling.E0_prod = (sum([product.conformer.E0.value_si
                                      for product in self.reaction.products]) * 0.001, "kJ/mol")
        elif tunneling is not None:
            if tunneling.frequency is not None:
                # Frequency was given by the user
                pass
            else:
                raise ValueError('Unknown tunneling model {0!r} for reaction {1}.'.format(tunneling, self.reaction))
        logging.debug('Generating {0} kinetics model for {1}...'.format(kineticsClass, self.reaction))
        klist = numpy.zeros_like(self.Tlist.value_si)
        for i, t in enumerate(self.Tlist.value_si):
            klist[i] = self.reaction.calculateTSTRateCoefficient(t)
        order = len(self.reaction.reactants)
        klist *= 1e6 ** (order - 1)
        self.kunits = {1: 's^-1', 2: 'cm^3/(mol*s)', 3: 'cm^6/(mol^2*s)'}[order]
        self.Kequnits = {2: 'mol^2/cm^6', 1: 'mol/cm^3', 0: '       ', -1: 'cm^3/mol', -2: 'cm^6/mol^2'}[
            len(self.reaction.products) - len(self.reaction.reactants)]
        self.krunits = {1: 's^-1', 2: 'cm^3/(mol*s)', 3: 'cm^6/(mol^2*s)'}[len(self.reaction.products)]
        self.reaction.kinetics = Arrhenius().fitToData(self.Tlist.value_si, klist, kunits=self.kunits)
        self.reaction.elementary_high_p = True

    def write_output(self, output_directory):
        """
        Save the results of the kinetics job to the `output.py` file located
        in `output_directory`.
        """
        reaction = self.reaction

        ks = []
        k0s = []
        k0revs = []
        krevs = []

        logging.info('Saving kinetics for {0}...'.format(reaction))

        order = len(self.reaction.reactants)

        factor = 1e6 ** (order - 1)

        f = open(os.path.join(output_directory, 'output.py'), 'a')

        if self.usedTST:
            # If TST is not used, eg. it was given in 'reaction', then this will throw an error.
            f.write('#   ======= =========== =========== =========== ===============\n')
            f.write('#   Temp.   k (TST)     Tunneling   k (TST+T)   Units\n')
            f.write('#   ======= =========== =========== =========== ===============\n')

            if self.Tlist is None:
                Tlist = numpy.array([300, 400, 500, 600, 800, 1000, 1500, 2000])
            else:
                Tlist = self.Tlist.value_si

            for T in Tlist:
                tunneling = reaction.transitionState.tunneling
                reaction.transitionState.tunneling = None
                try:
                    k0 = reaction.calculateTSTRateCoefficient(T) * factor
                except SpeciesError:
                    k0 = 0
                reaction.transitionState.tunneling = tunneling
                try:
                    k = reaction.calculateTSTRateCoefficient(T) * factor
                    kappa = k / k0
                except (SpeciesError, ZeroDivisionError):
                    k = reaction.getRateCoefficient(T)
                    kappa = 0
                    logging.info("The species in reaction {0} do not have adequate information for TST, "
                                 "using default kinetics values.".format(reaction))
                tunneling = reaction.transitionState.tunneling
                ks.append(k)
                k0s.append(k0)

                f.write('#    {0:4g} K {1:11.3e} {2:11g} {3:11.3e} {4}\n'.format(T, k0, kappa, k, self.kunits))
            f.write('#   ======= =========== =========== =========== ===============\n')
            f.write('\n\n')

            f.write('#   ======= ============ =========== ============ ============= =========\n')
            f.write('#   Temp.    Kc (eq)        Units     krev (TST)   krev (TST+T)   Units\n')
            f.write('#   ======= ============ =========== ============ ============= =========\n')

            # Initialize Object for Converting Units
            if self.Kequnits != '       ':
                keq_unit_converter = quantity.Units(self.Kequnits).getConversionFactorFromSI()
            else:
                keq_unit_converter = 1

            for n, T in enumerate(Tlist):
                k = ks[n]
                k0 = k0s[n]
                Keq = keq_unit_converter * reaction.getEquilibriumConstant(T)  # getEquilibriumConstant returns SI units
                k0rev = k0 / Keq
                krev = k / Keq
                k0revs.append(k0rev)
                krevs.append(krev)
                f.write('#    {0:4g} K {1:11.3e}   {2}  {3:11.3e}   {4:11.3e}      {5}\n'.format(
                    T, Keq, self.Kequnits, k0rev, krev, self.krunits))

            f.write('#   ======= ============ =========== ============ ============= =========\n')
            f.write('\n\n')

            kinetics0rev = Arrhenius().fitToData(Tlist, numpy.array(k0revs), kunits=self.krunits)
            kineticsrev = Arrhenius().fitToData(Tlist, numpy.array(krevs), kunits=self.krunits)

            f.write('# krev (TST) = {0} \n'.format(kinetics0rev))
            f.write('# krev (TST+T) = {0} \n\n'.format(kineticsrev))
        # Reaction path degeneracy is INCLUDED in the kinetics itself!
        rxn_str = 'kinetics(label={0!r}, kinetics={1!r})'.format(reaction.label, reaction.kinetics)
        f.write('{0}\n\n'.format(prettify(rxn_str)))

        f.close()

    def write_chemkin(self, output_directory):
        """
        Appends the kinetics rates to `chem.inp` in `outut_directory`
        """

        # obtain a unit conversion factor
        order = len(self.reaction.reactants)
        factor = 1e6 ** (order - 1)

        reaction = self.reaction
        kinetics = reaction.kinetics
        rxn_str = ''
        if reaction.kinetics.comment:
            for line in reaction.kinetics.comment.split("\n"):
                rxn_str += "! {0}\n".format(line)
        rxn_str += '{0!s:51} {1:9.3e} {2:9.3f} {3:9.3f}\n'.format(
            reaction,
            kinetics.A.value_si * factor,
            kinetics.n.value_si,
            kinetics.Ea.value_si / 4184.,
        )

        with open(os.path.join(output_directory, 'chem.inp'), 'a') as f:
            f.write('{0}\n'.format(rxn_str))

    def save_yaml(self, output_directory):
        """
        Save a YAML file for TSs if structures of the respective reactant/s and product/s are known
        """
        if all ([spc.molecule is not None and len(spc.molecule)
                 for spc in self.reaction.reactants + self.reaction.products]):
            self.arkane_species.update_species_attributes(self.reaction.transitionState)
            self.arkane_species.reaction_label = self.reaction.label
            self.arkane_species.reactants = [{'label': spc.label, 'adjacency_list': spc.molecule[0].toAdjacencyList()}
                                             for spc in self.reaction.reactants]
            self.arkane_species.products = [{'label': spc.label, 'adjacency_list': spc.molecule[0].toAdjacencyList()}
                                             for spc in self.reaction.products]
            self.arkane_species.save_yaml(path=output_directory)

    def plot(self, output_directory):
        """
        Plot both the raw kinetics data and the Arrhenius fit versus 
        temperature. The plot is saved to the file ``kinetics.pdf`` in the
        output directory. The plot is not generated if ``matplotlib`` is not
        installed.
        """
        import matplotlib.pyplot as plt

        f, ax = plt.subplots()
        if self.Tlist is not None:
            t_list = [t for t in self.Tlist.value_si]
        else:
            t_list = 1000.0 / numpy.arange(0.4, 3.35, 0.05)
        klist = numpy.zeros_like(t_list)
        klist2 = numpy.zeros_like(t_list)
        for i in xrange(len(t_list)):
            klist[i] = self.reaction.calculateTSTRateCoefficient(t_list[i])
            klist2[i] = self.reaction.kinetics.getRateCoefficient(t_list[i])

        order = len(self.reaction.reactants)
        klist *= 1e6 ** (order - 1)
        klist2 *= 1e6 ** (order - 1)
        t_list = [1000.0 / t for t in t_list]
        plt.semilogy(t_list, klist, 'ob', label='TST calculation')
        plt.semilogy(t_list, klist2, '-k', label='Fitted rate')
        plt.legend()
        reaction_str = '{0} {1} {2}'.format(
            ' + '.join([reactant.label for reactant in self.reaction.reactants]),
            '<=>', ' + '.join([product.label for product in self.reaction.products]))
        plt.title(reaction_str)
        plt.xlabel('1000 / Temperature (K^-1)')
        plt.ylabel('Rate coefficient ({0})'.format(self.kunits))

        plot_path = os.path.join(output_directory, 'plots')

        if not os.path.exists(plot_path):
            os.mkdir(plot_path)
        valid_chars = "-_.()<=> %s%s" % (string.ascii_letters, string.digits)
        filename = ''.join(c for c in reaction_str if c in valid_chars) + '.pdf'
        plt.savefig(os.path.join(plot_path, filename))
        plt.close()

    def draw(self, output_directory, format='pdf'):
        """
        Generate a PDF drawing of the reaction.
        This requires that Cairo and its Python wrapper be available; if not,
        the drawing is not generated.

        You may also generate different formats of drawings, by changing format to
        one of the following: `pdf`, `svg`, `png`.
        """

        drawing_path = os.path.join(output_directory, 'paths')

        if not os.path.exists(drawing_path):
            os.mkdir(drawing_path)
        valid_chars = "-_.()<=> %s%s" % (string.ascii_letters, string.digits)
        reaction_str = '{0} {1} {2}'.format(
            ' + '.join([reactant.label for reactant in self.reaction.reactants]),
            '<=>', ' + '.join([product.label for product in self.reaction.products]))
        filename = ''.join(c for c in reaction_str if c in valid_chars) + '.pdf'
        path = os.path.join(drawing_path, filename)

        KineticsDrawer().draw(self.reaction, format=format, path=path)


class KineticsDrawer:
    """
    This class provides functionality for drawing the potential energy surface
    for a high pressure limit reaction using the Cairo 2D graphics engine.
    The most common use case is simply::

        KineticsDrawer().draw(reaction, format='png', path='network.png')

    where ``reaction`` is the :class:`Reaction` object to draw. You can also
    pass a dict of options to the constructor to affect how the reaction is drawn.
    """

    def __init__(self, options=None):
        self.options = {
            'structures': True,
            'fontFamily': 'sans',
            'fontSizeNormal': 12,
            'Eunits': 'kJ/mol',
            'padding': 16,
            'wellWidth': 64,
            'wellSpacing': 64,
            'Eslope': 1.5,
            'TSwidth': 16,
            'E0offset': 0.0,
        }
        if options:
            self.options.update(options)
        self.clear()

    def clear(self):
        """Clear the drawer"""
        self.reaction = None
        self.wells = None
        self.left = 0.0
        self.top = 0.0
        self.right = 0.0
        self.bottom = 0.0
        self.surface = None
        self.cr = None

    def __getEnergyRange(self):
        """
        Return the minimum and maximum energy in J/mol on the potential energy surface.
        """
        E0min = min(self.wells[0].E0, self.wells[1].E0, self.reaction.transitionState.conformer.E0.value_si)
        E0max = max(self.wells[0].E0, self.wells[1].E0, self.reaction.transitionState.conformer.E0.value_si)
        if E0max - E0min > 5e5:
            # the energy barrier in one of the reaction directions is larger than 500 kJ/mol, warn the user
            logging.warning('The energy differences between the stationary points of reaction {0} '
                            'seems too large.'.format(self.reaction))
            logging.warning('Got the following energies:\nWell 1: {0} kJ/mol\nTS: {1} kJ/mol\nWell 2: {2}'
                            ' kJ/mol'.format(self.wells[0].E0 / 1000., self.wells[1].E0 / 1000.,
                                             self.reaction.transitionState.conformer.E0.value_si / 1000.))
        return E0min, E0max

    def __useStructureForLabel(self, configuration):
        """
        Return ``True`` if the configuration should use molecular structures
        for its labels or ``False`` otherwise.
        """

        # Initialize with the current user option value
        useStructures = self.options['structures']

        # But don't use structures if one or more species in the configuration
        # do not have structure data
        for spec in configuration.species_list:
            if spec.molecule is None or len(spec.molecule) == 0:
                useStructures = False
                break

        return useStructures

    def __getTextSize(self, text, padding=2, format='pdf'):
        try:
            import cairocffi as cairo
        except ImportError:
            import cairo

        # Use dummy surface to determine text extents
        surface = createNewSurface(format)
        cr = cairo.Context(surface)
        cr.set_font_size(self.options['fontSizeNormal'])
        extents = cr.text_extents(text)
        width = extents[2] + 2 * padding
        height = extents[3] + 2 * padding
        return [0, 0, width, height]

    def __drawText(self, text, cr, x0, y0, padding=2):
        cr.save()
        cr.set_font_size(self.options['fontSizeNormal'])
        extents = cr.text_extents(text)
        cr.move_to(x0 - extents[0] - padding, y0 - extents[1] + padding)
        cr.set_source_rgba(0.0, 0.0, 0.0, 1.0)
        cr.show_text(text)
        cr.restore()
        width = extents[2] + 2 * padding
        height = extents[3] + 2 * padding
        return [0, 0, width, height]

    def __getLabelSize(self, configuration, format='pdf'):
        width = 0
        height = 0
        boundingRects = []
        if self.__useStructureForLabel(configuration):
            for spec in configuration.species_list:
                _, _, rect = MoleculeDrawer().draw(spec.molecule[0], format=format)
                boundingRects.append(list(rect))
        else:
            for spec in configuration.species_list:
                boundingRects.append(self.__getTextSize(spec.label, format=format))

        plusRect = self.__getTextSize('+', format=format)

        for rect in boundingRects:
            if width < rect[2]:
                width = rect[2]
            height += rect[3] + plusRect[3]
        height -= plusRect[3]

        return [0, 0, width, height]

    def __drawLabel(self, configuration, cr, x0, y0, format='pdf'):

        boundingRect = self.__getLabelSize(configuration, format=format)
        padding = 2

        useStructures = self.__useStructureForLabel(configuration)
        y = y0
        for i, spec in enumerate(configuration.species_list):
            if i > 0:
                rect = self.__getTextSize('+', padding=padding, format=format)
                x = x0 - 0.5 * (rect[2] - boundingRect[2]) + 2 * padding
                self.__drawText('+', cr, x, y)
                y += rect[3]

            if useStructures:
                moleculeDrawer = MoleculeDrawer()
                cr.save()
                _, _, rect = moleculeDrawer.draw(spec.molecule[0], format=format)
                cr.restore()
                x = x0 - 0.5 * (rect[2] - boundingRect[2])
                cr.save()
                moleculeDrawer.render(cr, offset=(x, y))
                cr.restore()
                y += rect[3]
            else:
                rect = self.__getTextSize(spec.label, padding=padding, format=format)
                x = x0 - 0.5 * (rect[2] - boundingRect[2]) + 2 * padding
                self.__drawText(spec.label, cr, x, y)
                y += rect[3]

        return boundingRect

    def draw(self, reaction, format, path=None):
        """
        Draw the potential energy surface for the given `network` as a Cairo
        surface of the given `format`. If `path` is given, the surface is
        saved to that location on disk.
        """
        try:
            import cairocffi as cairo
        except ImportError:
            try:
                import cairo
            except ImportError:
                logging.warning('Cairo not found; potential energy surface will not be drawn.')
                return

        self.reaction = reaction
        self.wells = [Well(self.reaction.reactants), Well(self.reaction.products)]

        # Generate the bounding rectangles for each configuration label
        labelRects = []
        for well in self.wells:
            labelRects.append(self.__getLabelSize(well, format=format))

        # Get energy range (use kJ/mol internally)
        E0min, E0max = self.__getEnergyRange()
        E0min *= 0.001
        E0max *= 0.001

        # Drawing parameters
        padding = self.options['padding']
        wellWidth = self.options['wellWidth']
        wellSpacing = self.options['wellSpacing']
        Eslope = self.options['Eslope']
        TSwidth = self.options['TSwidth']

        E0_offset = self.options['E0offset'] * 0.001

        # Choose multiplier to convert energies to desired units (on figure only)
        Eunits = self.options['Eunits']
        try:
            Emult = {'J/mol': 1.0, 'kJ/mol': 0.001, 'cal/mol': 1.0 / 4.184, 'kcal/mol': 1.0 / 4184.,
                     'cm^-1': 1.0 / 11.962}[Eunits]
        except KeyError:
            raise Exception('Invalid value "{0}" for Eunits parameter.'.format(Eunits))

        # Determine height required for drawing
        Eheight = self.__getTextSize('0.0', format=format)[3] + 6
        y_E0 = (E0max - 0.0) * Eslope + padding + Eheight
        height = (E0max - E0min) * Eslope + 2 * padding + Eheight + 6
        for i in xrange(len(self.wells)):
            if 0.001 * self.wells[i].E0 == E0min:
                height += labelRects[i][3]
                break

        # Determine naive position of each well (one per column)
        coordinates = numpy.zeros((len(self.wells), 2), numpy.float64)
        x = padding
        for i in xrange(len(self.wells)):
            well = self.wells[i]
            rect = labelRects[i]
            thisWellWidth = max(wellWidth, rect[2])
            E0 = 0.001 * well.E0
            y = y_E0 - E0 * Eslope
            coordinates[i] = [x + 0.5 * thisWellWidth, y]
            x += thisWellWidth + wellSpacing
        width = x + padding - wellSpacing

        # Determine the rectangles taken up by each well
        # We'll use this to merge columns safely so that wells don't overlap
        wellRects = []
        for i in range(len(self.wells)):
            l, t, w, h = labelRects[i]
            x, y = coordinates[i, :]
            if w < wellWidth:
                w = wellWidth
            t -= 6 + Eheight
            h += 6 + Eheight
            wellRects.append([l + x - 0.5 * w, t + y + 6, w, h])

        # Squish columns together from the left where possible until an isomer is encountered
        oldLeft = numpy.min(coordinates[:, 0])
        Nleft = - 1
        columns = []
        for i in range(Nleft, -1, -1):
            top = wellRects[i][1]
            bottom = top + wellRects[i][3]
            for column in columns:
                for c in column:
                    top0 = wellRects[c][1]
                    bottom0 = top + wellRects[c][3]
                    if (top0 <= top <= bottom0) or (top <= top0 <= bottom):
                        # Can't put it in this column
                        break
                else:
                    # Can put it in this column
                    column.append(i)
                    break
            else:
                # Needs a new column
                columns.append([i])
        for column in columns:
            columnWidth = max([wellRects[c][2] for c in column])
            x = coordinates[column[0] + 1, 0] - 0.5 * wellRects[column[0] + 1][2] - wellSpacing - 0.5 * columnWidth
            for c in column:
                delta = x - coordinates[c, 0]
                wellRects[c][0] += delta
                coordinates[c, 0] += delta
        newLeft = numpy.min(coordinates[:, 0])
        coordinates[:, 0] -= newLeft - oldLeft

        # Squish columns together from the right where possible until an isomer is encountered
        Nright = 3
        columns = []
        for i in range(Nright, len(self.wells)):
            top = wellRects[i][1]
            bottom = top + wellRects[i][3]
            for column in columns:
                for c in column:
                    top0 = wellRects[c][1]
                    bottom0 = top0 + wellRects[c][3]
                    if (top0 <= top <= bottom0) or (top <= top0 <= bottom):
                        # Can't put it in this column
                        break
                else:
                    # Can put it in this column
                    column.append(i)
                    break
            else:
                # Needs a new column
                columns.append([i])
        for column in columns:
            columnWidth = max([wellRects[c][2] for c in column])
            x = coordinates[column[0] - 1, 0] + 0.5 * wellRects[column[0] - 1][2] + wellSpacing + 0.5 * columnWidth
            for c in column:
                delta = x - coordinates[c, 0]
                wellRects[c][0] += delta
                coordinates[c, 0] += delta

        width = max([rect[2] + rect[0] for rect in wellRects]) - min([rect[0] for rect in wellRects]) + 2 * padding

        # Draw to the final surface
        surface = createNewSurface(format=format, target=path, width=width, height=height)
        cr = cairo.Context(surface)

        # Some global settings
        cr.select_font_face("sans")
        cr.set_font_size(self.options['fontSizeNormal'])

        # Fill the background with white
        cr.set_source_rgba(1.0, 1.0, 1.0, 1.0)
        cr.paint()
        self.__drawText('E0 ({0})'.format(Eunits), cr, 15, 10, padding=2)  # write units

        # Draw reactions
        E0_reac = self.wells[0].E0 * 0.001 - E0_offset
        E0_prod = self.wells[1].E0 * 0.001 - E0_offset
        E0_TS = self.reaction.transitionState.conformer.E0.value_si * 0.001 - E0_offset
        x1, y1 = coordinates[0, :]
        x2, y2 = coordinates[1, :]
        x1 += wellSpacing / 2.0
        x2 -= wellSpacing / 2.0
        if abs(E0_TS - E0_reac) > 0.1 and abs(E0_TS - E0_prod) > 0.1:
            if len(self.reaction.reactants) == 2:
                if E0_reac < E0_prod:
                    x0 = x1 + wellSpacing * 0.5
                else:
                    x0 = x2 - wellSpacing * 0.5
            elif len(self.reaction.products) == 2:
                if E0_reac < E0_prod:
                    x0 = x2 - wellSpacing * 0.5
                else:
                    x0 = x1 + wellSpacing * 0.5
            else:
                x0 = 0.5 * (x1 + x2)
            y0 = y_E0 - (E0_TS + E0_offset) * Eslope
            width1 = (x0 - x1)
            width2 = (x2 - x0)
            # Draw horizontal line for TS
            cr.set_source_rgba(0.0, 0.0, 0.0, 1.0)
            cr.set_line_width(2.0)
            cr.move_to(x0 - TSwidth / 2.0, y0)
            cr.line_to(x0 + TSwidth / 2.0, y0)
            cr.stroke()
            # Add background and text for energy
            E0 = "{0:.1f}".format(E0_TS * 1000. * Emult)
            extents = cr.text_extents(E0)
            x = x0 - extents[2] / 2.0
            y = y0 - 6.0
            cr.rectangle(x + extents[0] - 2.0, y + extents[1] - 2.0, extents[2] + 4.0, extents[3] + 4.0)
            cr.set_source_rgba(1.0, 1.0, 1.0, 0.75)
            cr.fill()
            cr.move_to(x, y)
            cr.set_source_rgba(0.0, 0.0, 0.0, 1.0)
            cr.show_text(E0)
            # Draw Bezier curve connecting reactants and products through TS
            cr.set_source_rgba(0.0, 0.0, 0.0, 0.5)
            cr.set_line_width(1.0)
            cr.move_to(x1, y1)
            cr.curve_to(x1 + width1 / 8.0, y1, x0 - width1 / 8.0 - TSwidth / 2.0, y0, x0 - TSwidth / 2.0, y0)
            cr.move_to(x0 + TSwidth / 2.0, y0)
            cr.curve_to(x0 + width2 / 8.0 + TSwidth / 2.0, y0, x2 - width2 / 8.0, y2, x2, y2)
            cr.stroke()
        else:
            width = (x2 - x1)
            # Draw Bezier curve connecting reactants and products through TS
            cr.set_source_rgba(0.0, 0.0, 0.0, 0.5)
            cr.set_line_width(1.0)
            cr.move_to(x1, y1)
            cr.curve_to(x1 + width / 4.0, y1, x2 - width / 4.0, y2, x2, y2)
            cr.stroke()

        # Draw wells (after path reactions so that they are on top)
        for i, well in enumerate(self.wells):
            x0, y0 = coordinates[i, :]
            # Draw horizontal line for well
            cr.set_line_width(4.0)
            cr.move_to(x0 - wellWidth / 2.0, y0)
            cr.line_to(x0 + wellWidth / 2.0, y0)
            cr.set_source_rgba(0.0, 0.0, 0.0, 1.0)
            cr.stroke()
            # Add background and text for energy
            E0 = well.E0 * 0.001 - E0_offset
            E0 = "{0:.1f}".format(E0 * 1000. * Emult)
            extents = cr.text_extents(E0)
            x = x0 - extents[2] / 2.0
            y = y0 - 6.0
            cr.rectangle(x + extents[0] - 2.0, y + extents[1] - 2.0, extents[2] + 4.0, extents[3] + 4.0)
            cr.set_source_rgba(1.0, 1.0, 1.0, 0.75)
            cr.fill()
            cr.move_to(x, y)
            cr.set_source_rgba(0.0, 0.0, 0.0, 1.0)
            cr.show_text(E0)
            # Draw background and text for label
            x = x0 - 0.5 * labelRects[i][2]
            y = y0 + 6
            cr.rectangle(x, y, labelRects[i][2], labelRects[i][3])
            cr.set_source_rgba(1.0, 1.0, 1.0, 0.75)
            cr.fill()
            self.__drawLabel(well, cr, x, y, format=format)

        # Finish Cairo drawing
        if format == 'png':
            surface.write_to_png(path)
        else:
            surface.finish()


class Well:
    """
    A helper class representing a "well" of species
    `species_list` is a list of at least one entry
    `E0 `is the sum of all species' E0 in that list
    """

    def __init__(self, species_list):
        self.species_list = species_list
        self.E0 = sum([species.conformer.E0.value_si for species in species_list])
