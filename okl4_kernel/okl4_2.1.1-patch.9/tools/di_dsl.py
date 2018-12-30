#!/usr/bin/env python
##############################################################################
# Copyright (c) 2007 Open Kernel Labs, Inc. (Copyright Holder).
# All rights reserved.
# 
# 1. Redistribution and use of OKL4 (Software) in source and binary
# forms, with or without modification, are permitted provided that the
# following conditions are met:
# 
#     (a) Redistributions of source code must retain this clause 1
#         (including paragraphs (a), (b) and (c)), clause 2 and clause 3
#         (Licence Terms) and the above copyright notice.
# 
#     (b) Redistributions in binary form must reproduce the above
#         copyright notice and the Licence Terms in the documentation and/or
#         other materials provided with the distribution.
# 
#     (c) Redistributions in any form must be accompanied by information on
#         how to obtain complete source code for:
#        (i) the Software; and
#        (ii) all accompanying software that uses (or is intended to
#        use) the Software whether directly or indirectly.  Such source
#        code must:
#        (iii) either be included in the distribution or be available
#        for no more than the cost of distribution plus a nominal fee;
#        and
#        (iv) be licensed by each relevant holder of copyright under
#        either the Licence Terms (with an appropriate copyright notice)
#        or the terms of a licence which is approved by the Open Source
#        Initative.  For an executable file, "complete source code"
#        means the source code for all modules it contains and includes
#        associated build and other files reasonably required to produce
#        the executable.
# 
# 2. THIS SOFTWARE IS PROVIDED ``AS IS'' AND, TO THE EXTENT PERMITTED BY
# LAW, ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
# THE IMPLIED WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR
# PURPOSE, OR NON-INFRINGEMENT, ARE DISCLAIMED.  WHERE ANY WARRANTY IS
# IMPLIED AND IS PREVENTED BY LAW FROM BEING DISCLAIMED THEN TO THE
# EXTENT PERMISSIBLE BY LAW: (A) THE WARRANTY IS READ DOWN IN FAVOUR OF
# THE COPYRIGHT HOLDER (AND, IN THE CASE OF A PARTICIPANT, THAT
# PARTICIPANT) AND (B) ANY LIMITATIONS PERMITTED BY LAW (INCLUDING AS TO
# THE EXTENT OF THE WARRANTY AND THE REMEDIES AVAILABLE IN THE EVENT OF
# BREACH) ARE DEEMED PART OF THIS LICENCE IN A FORM MOST FAVOURABLE TO
# THE COPYRIGHT HOLDER (AND, IN THE CASE OF A PARTICIPANT, THAT
# PARTICIPANT). IN THE LICENCE TERMS, "PARTICIPANT" INCLUDES EVERY
# PERSON WHO HAS CONTRIBUTED TO THE SOFTWARE OR WHO HAS BEEN INVOLVED IN
# THE DISTRIBUTION OR DISSEMINATION OF THE SOFTWARE.
# 
# 3. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR ANY OTHER PARTICIPANT BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR
# BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE
# OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN
# IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
###############################################################################

###############################################################################
#
# Generate the interface file for a driver based on it's XML spec (normally
# in an "*_if.di" file).
#
###############################################################################
import sys, sets
from ezxml import Element, long_attr, str_attr

def uniq(lst):
    return list(sets.Set(lst))

################################################################################
# Define the XML elements
################################################################################
datafield_el = Element("datafield",
                       ftype=(str_attr, "required"),
                       name=(str_attr, "required"))

arg_el = Element("arg",
                 atype=(str_attr, "required"),
                 name=(str_attr, "required"))

method_el = Element("method", arg_el,
                 name=(str_attr, "required"),
                 rtype=(str_attr, "required")
                 )

interface_el = Element("interface", method_el, datafield_el,
                       name=(str_attr, "required"))


################################################################################
# Templates
################################################################################
file_header = """/* WARNING: Autogenerated file. Do not edit.
 *
 * This file crated by di_dsl.py from %(file)s
 *
 */

#ifndef _%(name)s_IF_H
#define _%(name)s_IF_H
#else
#error File should only be included via concrete header for module
#endif

#include <stdint.h>
/* Forward declaration */
struct %(name)s_interface;

/* Interface methods */
"""

interface_struct = """struct %(name)s_interface {
    int interface_type;
    void *device;
    struct %(name)s_ops ops;
"""

typedef = "typedef %(rtype)s (*%(if_name)s_%(name)s_fn)(struct %(if_name)s_interface *, void *%(argtype)s);\n"

inline_fn = """
static inline %(rtype)s
%(if_name)s_%(name)s(struct %(if_name)s_interface *interface%(argspec)s)
{
    %(return)sinterface->ops.%(name)s(interface, interface->device%(arglist)s);
}
"""

proto_setup = "    static %(rtype)s %(if_name)s_%(name)s_impl(struct %(if_name)s_interface *, struct DEV_NAME *%(argtype)s); \\\n"

################################################################################
# The actual parsing stuff
################################################################################
class InterfaceFile:
    def __init__(self, file, output_file):
        interface = interface_el.parse_xml_file(file)
        output = open(output_file, "w")
        
        self.name = name = interface.name
        methods = interface.find_children("method")

        output.write(file_header % {"file":file, "name":name })
        for method in methods:
            output.write(typedef % self.get_method_dict(method))

        output.write("\n/* Method table */\n")
        output.write("struct %s_ops {\n" % name)
        for method in methods:
            output.write("    %s_%s_fn %s;\n" % (name, method.name, method.name))
        output.write("};\n\n")

        output.write(interface_struct % {"name":name})
        for field in interface.find_children("datafield"):
            output.write("    %s %s;\n" % (field.ftype, field.name))
        output.write("};\n\n")

        output.write("#define SETUP_%s_PROTOS(DEV_NAME) \\\n" % name.upper())
        for method in methods:
            output.write(proto_setup % self.get_method_dict(method))
        output.write("\n\n")

        output.write("#define SETUP_%s_OPS() \\\n" % name.upper())
        output.write("    static struct %s_ops %s_ops = { \\\n" % (name, name))
        for method in methods:
            output.write("        (%s_%s_fn) %s_%s_impl, \\\n" % (name, method.name, name, method.name))
        output.write("    };\n\n")

        for method in methods:
            output.write(inline_fn % self.get_method_dict(method));

    def get_method_dict(self, method):
        """Return a dictionary to be used for string substitution"""
        method_dict =  {"rtype":method.rtype,
                        "if_name":self.name,
                        "name":method.name,
                        "arglist":self.get_arglist(method),
                        "argtype":self.get_argtype(method),
                        "argspec":self.get_argspec(method)}
        if method.rtype == "void":
            method_dict["return"] = ""
        else:
            method_dict["return"] = "return "
        return method_dict

    def get_argspec(self, method):
        """Return the argspec of a given method"""
        argspec = ""
        for arg in method.find_children("arg"):
            argspec += ", %s %s" % (arg.atype, arg.name)
        return argspec

    def get_arglist(self, method):
        """Return the arglist for a given method"""
        arglist = ""
        for arg in method.find_children("arg"):
            arglist += ", %s" % (arg.name)
        return arglist

    def get_argtype(self, method):
        """Return the arglist for a given method"""
        arglist = ""
        for arg in method.find_children("arg"):
            arglist += ", %s" % (arg.atype)
        return arglist

r = InterfaceFile(sys.argv[1], sys.argv[2])
