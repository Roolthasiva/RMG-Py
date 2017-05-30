#!/usr/bin/env python
# encoding: utf-8

################################################################################
#
#   RMG - Reaction Mechanism Generator
#
#   Copyright (c) 2002-2017 Prof. William H. Green (whgreen@mit.edu),
#   Prof. Richard H. West (r.west@neu.edu) and the RMG Team (rmg_dev@mit.edu)
#
#   Permission is hereby granted, free of charge, to any person obtaining a
#   copy of this software and associated documentation files (the 'Software'),
#   to deal in the Software without restriction, including without limitation
#   the rights to use, copy, modify, merge, publish, distribute, sublicense,
#   and/or sell copies of the Software, and to permit persons to whom the
#   Software is furnished to do so, subject to the following conditions:
#
#   The above copyright notice and this permission notice shall be included in
#   all copies or substantial portions of the Software.
#
#   THE SOFTWARE IS PROVIDED 'AS IS', WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#   IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#   FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#   AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#   LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
#   FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
#   DEALINGS IN THE SOFTWARE.
#
################################################################################

import os.path
import os
import Tkinter as tk
import tkFileDialog as tkFD
import tkFont
import logging
import rmgpy
from rmgpy.rmg.main import RMG, initializeLog, processProfileStats, makeProfileGraph


class RMG_GUI(tk.Frame):
    """Create an RMG_GUI window using the tkinter library in Python"""


    def __init__(self, parent):
        self.frame = tk.Frame(parent)
        self.frame.grid()

        self.parent = parent
        self.parent.title("Reaction Mechanism Generator GUI")
        self.screen_width = self.parent.winfo_screenwidth()
        self.screen_height = self.parent.winfo_screenheight()
        self.window_width = self.screen_width/2
        self.window_height = (self.screen_height/4)*3
        self.xpos = (self.screen_width-self.window_width)/2
        self.ypos = (self.screen_height-self.window_height)/2
        self.parent.geometry('{0}x{1}+{2}+{3}'.format(self.window_width, self.window_height, self.xpos, self.ypos))
        self.main_options = ('Generate a Mechanism (Run RMG)', 'Run Cantera on an Existing Mechanism',
                             'Analyze an Existing Mechanism')
        self.font = tkFont.Font(family='Times', size=18)
        self.main_selection = tk.StringVar(value=self.main_options[0])

        self.main_menu_UI()

    def main_menu_UI(self):
        """Place the tkinter widgets for the main menu in the GUI window."""
        self.intro_text =\
'''
Welcome to the graphical user inteface for the Reaction Mechanism Generator (RMG). From here you can start an RMG job \
by editing an existing input file or by creating a new input file from scratch. You can also run a Cantera job on an \
exisiting mechanism, or analyze the mechanism using built-in RMG tools such as sensitivity analysis or pathway \
analysis. To begin, please select an option from the dropdown menu below:
        
        
'''
        self.intro_message = tk.Message(self.frame, text=self.intro_text, width=self.window_width*0.95, font=self.font)
        self.intro_message.grid(row=0, column=0, columnspan=3)

        self.main_option_box = tk.OptionMenu(self.frame, self.main_selection, *self.main_options)
        self.main_option_box.grid(row=1, column=1)
        self.main_option_box.configure(font=self.font)
        self.main_next_button = tk.Button(self.frame, text='Next', command=self.advance_main_menu)
        self.main_next_button.configure(width=10, height=2, font=self.font)
        self.main_next_button.grid(row=5, column=1)

    def main_menu_UI_Off(self):
        """Remove main menu widgets from the window"""
        self.intro_message.grid_forget()
        self.main_option_box.grid_forget()
        self.main_next_button.grid_forget()

    def advance_main_menu(self):
        """Get the user's selection from main menu option box and advance to the requested interface"""
        user_selection = self.main_selection.get()
        self.main_menu_UI_Off()

        if user_selection == self.main_options[0]: # if 'Run RMG' is selected
            self.run_RMG_main_UI()

        else:
            self.frame.quit()

    def run_RMG_main_UI(self):
        """Place the tkinter widgets for selecting the input file method for the RMG job"""
        self.choose_RMG_method_text = \
'''
Run an RMG Job:

You can choose to run an RMG job from an existing input file, or create a new input file using the GUI. Please \
make your selection below:
'''
        self.choose_RMG_method_message = tk.Message(self.frame, text=self.choose_RMG_method_text)
        self.choose_RMG_method_message.configure(width=self.window_width*0.95, font=self.font)
        self.choose_RMG_method_message.grid(row=0, column=0, columnspan=3)

        self.RMG_method_options = ('From an existing input file', 'Create a new input file using the GUI')
        self.RMG_method_selection = tk.StringVar(value=self.RMG_method_options[0])
        self.RMG_method_optionbox = tk.OptionMenu(self.frame, self.RMG_method_selection, *self.RMG_method_options)
        self.RMG_method_optionbox.configure(font=self.font)
        self.RMG_method_optionbox.grid(row=1, column=1)

        self.RMG_method_next_button = tk.Button(self.frame, text='Next', command=self.advance_RMG_method_menu)
        self.RMG_method_next_button.configure(width=10, height=2, font=self.font)
        self.RMG_method_next_button.grid(row=2, column=1)

    def run_RMG_main_UI_off(self):
        self.choose_RMG_method_message.grid_forget()
        self.RMG_method_optionbox.grid_forget()
        self.RMG_method_next_button.grid_forget()

    def advance_RMG_method_menu(self):
        """Get the user's selection for input file method and advance to the requested interface"""
        selection = self.RMG_method_selection.get()
        self.run_RMG_main_UI_off()
        if selection == self.RMG_method_options[0]:
            self.load_input_file_UI()

        else:
            self.frame.quit()

    def load_input_file_UI(self):
        """Place tkinter widgets for loading existing input file"""
        self.load_input_file_UI_text = \
'''
Run an RMG job from an exisitng file:

Please select a file below:
'''

        self.load_input_file_UI_message = tk.Message(self.frame, text=self.load_input_file_UI_text)
        self.load_input_file_UI_message.configure(width=self.window_width*0.95, font=self.font)
        self.load_input_file_UI_message.grid(row=0, column=0, columnspan=3)

        self.input_file_location = tk.StringVar(value='')
        self.input_file_entry = tk.Entry(self.frame, textvariable=self.input_file_location)
        #self.input_file_entry.configure(width=100)
        self.input_file_entry.grid(row=1, column=0, columnspan=3)

        self.input_file_browse = tk.Button(self.frame, text='Browse', command=self.open_input_file)
        self.input_file_browse.configure(width=10, font=self.font)
        self.input_file_browse.grid(row=1, column=3)

        self.output_directory_location = tk.StringVar(value='')
        self.output_directory_entry = tk.Entry(self.frame, textvariable=self.output_directory_location)
        self.output_directory_entry.grid(row=2, column=0, columnspan=3)

        self.output_directory_browse =tk.Button(self.frame, text='Browse', command=self.open_output_directory)
        self.output_directory_browse.configure(width=10, font=self.font)
        self.output_directory_browse.grid(row=2, column=3)

        self.run_RMG_button = tk.Button(self.frame, text='Run RMG Job', command=self.RMG_submit_job)
        self.run_RMG_button.configure(width=10, height=2, font=self.font)
        self.run_RMG_button.grid(row=3, column=2)

        self.kwargs = {'scratch_directory':''}

    def load_input_file_UI_off(self):
        self.load_input_file_UI_message.grid_forget()
        self.input_file_entry.grid_forget()
        self.input_file_browse.grid_forget()
        self.output_directory_entry.grid_forget()
        self.output_directory_browse.grid_forget()
        self.run_RMG_button.grid_forget()

    def open_input_file(self):
        tk.Tk().withdraw()
        self.input_file_location.set(tkFD.askopenfilename())
        self.output_directory_location.set(os.path.abspath(os.path.dirname(self.input_file_location.get())))
        self.kwargs['scratch_directory'] = self.output_directory_location.get()

    def open_output_directory(self):
        tk.Tk().withdraw()
        self.output_directory_location.set(tkFD.askdirectory())
        self.kwargs['scratch_directory'] = self.output_directory_location.get()

    def RMG_submit_job(self):
        self.load_input_file_UI_off()
        self.RMG_job_submitted_UI()
        self.parent.after(1000,self.run_RMG_job())

    def run_RMG_job(self):
        initializeLog(logging.INFO, os.path.join(self.output_directory_location.get(), 'RMG.log'))
        logging.info(rmgpy.settings.report())

        self.rmg = RMG(inputFile=self.input_file_location.get(), outputDirectory=self.output_directory_location.get())
        self.rmg.execute(**self.kwargs)
        self.frame.quit()

    def RMG_job_submitted_UI(self):
        self.RMG_job_submitted_text = \
'''
Your RMG job has been succesfully submitted. You can view the RMG log from the commandline, or by viewing the RMG.log \
file in the specified output directory
'''

        self.RMG_job_submitted_message = tk.Message(self.frame, text=self.RMG_job_submitted_text)
        self.RMG_job_submitted_message.configure(width=0.95*self.window_width, font=self.font)
        self.RMG_job_submitted_message.grid()


def main():

    root = tk.Tk()
    app = RMG_GUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()
