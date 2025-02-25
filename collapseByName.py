# Collapse By Name v1.2
# Authored by Josh Hollander and Avery Brown
#
# Gathers all objects in the scene, grouping them by name.  Objects with the exact same name will be merged together.
# Useful for consolidating Revit models.
#
# Inspiration for part of this code comes from ScriptSpot user antomor, and his Quick Attach MAXScript.

# Import PyMXS, and set up shorthand vars

# from __future__ import unicode_literals

import pymxs
import traceback
import re
from math import log10

maxscript = pymxs.runtime.execute
rt = pymxs.runtime

# Maxscript snippet to return an array of instances
# Maxscript uses a pass by reference parameter to return this value,
# making it incompatible with the current PyMXS implementation
maxscript(
    "fn rf_getInstances obj = ("
    "    InstanceMgr.GetInstances obj &instances"
    "    return instances"
    ")"
)

# ==================================================
#                    Flags
# ==================================================

SKIP_INSTANCE = True
IGNORE_BRACKET_DIGITS = True
USE_SELECTION = False


# ==================================================
#                    Functions
# ==================================================

# Calculates the number of digits in a number
# Based on a stack overflow answer by John La Rooy
# https://stackoverflow.com/a/2189827/15062519
def magnitude_of_number(n):
    if n > 0:
        return int(log10(n)) + 1
    elif n == 0:
        return 1
    else:
        return int(log10(-n)) + 1  # +1 if you don't count the '-'


def collapse_objects(obj_list):
    # NOTE: This function will cause 3ds Max to crash if it's passed a list of length 1.  I have no idea why.
    # First make sure we weren't passed an empty list
    if not obj_list:
        return None

    # DEBUG
    # print(len(obj_list))

    # Next make sure we weren't passed a list with only one object.  For reasons unknown to me, this will crash Max.
    if len(obj_list) == 1:
        return obj_list[0]

    # Create an empty Editable Mesh object to attach to, put it on the same layer as our objects
    layer = obj_list[0].layer
    root = rt.Editable_Mesh()
    root.name = obj_list[0].name
    layer.addNode(root)

    # Make sure the object is attachable, then attach it to root
    for obj in obj_list:
        if rt.SuperClassOf(obj) == rt.GeometryClass and rt.IsValidNode(obj):
            rt.meshop.attach(root, obj, condenseMat=True, deleteSourceNode=True, attachMat=rt.name("IDToMat"))

    rt.gc()
    return root


def run():
    # ==================================================
    #                 Collect Objects
    # ==================================================

    # Allows choosing between selection and the full scene
    objs = rt.getCurrentSelection() if USE_SELECTION else rt.geometry

    total_objs = len(objs)
    unique_objs_sorted = {}
    instances_sorted = {}
    num_instances = 0
    num_unique_objs = 0

    # Regex for finding bracketed digits
    remove_brackets_re = re.compile(r"\s*\[[\d]+?].*")

    # Iterate over all objects, sorting them into groups by name
    print("Examining %s Scene Objects..." % total_objs)
    milestone_examine = (total_objs / 100)
    for i, obj in enumerate(objs):
        name = remove_brackets_re.sub(u'', obj.name) if IGNORE_BRACKET_DIGITS else obj.name
        # In order to support unicode characters properly in the dictionary, non-ascii characters
        # are encoded to their xml versions (for example: &#163 for a pound sterling sign),
        # which allows objects to retain unique dictionary keys.
        name.encode('ascii', 'xmlcharrefreplace')
        try:
            # Tests if an object is an instance or not
            if SKIP_INSTANCE and len(rt.rf_getInstances(obj)) > 1:
                try:
                    num_instances += 1
                    instances_sorted[name].append(obj)
                except KeyError:
                    # Adds the Key to the dictionary if it doesn't already exist
                    instances_sorted[name] = []
                    instances_sorted[name].append(obj)
            # Unique Objects
            else:
                try:
                    num_unique_objs += 1
                    unique_objs_sorted[name].append(obj)
                except KeyError:
                    # Adds the Key to the dictionary if it doesn't already exist
                    unique_objs_sorted[name] = []
                    unique_objs_sorted[name].append(obj)
            # Prevent Max from hanging
            rt.windows.processPostedMessages()

        # Not sure if this try block is needed, but here is a general
        # catcher for exceptions thrown while analyzing the scene
        except Exception as ex:
            print('Error: %s with Object: "%s" %s' % (ex, name, obj))
            traceback.print_exc()

        finally:
            if i > milestone_examine:
                print("%d%%  -  Examining..." % (
                    round((i * 100) / total_objs)
                      ))
                milestone_examine = milestone_examine + (total_objs / 100)

    print("100% - Done")

    # ==================================================
    #                 Collapse Groups
    # ==================================================

    print("Collapsing Objects...")

    with pymxs.undo(False), pymxs.redraw(False):
        try:
            # TODO: Set batch size programmatically, based on the total number of objects?
            batch = 100
            objs_processed = 0
            instances_processed = 0
            milestone_collapse = num_unique_objs / 100
            milestone_naming = num_instances / 100

            for i, group in enumerate(unique_objs_sorted.values()):
                # print("%d%%  -  Collapsing %s" % (
                #     min(100, ((100 * objs_processed) / num_unique_objs)),
                #     group[0].name
                # ))

                group_count = len(group)

                if group_count > batch:
                    meshes = []
                    for x in range(0, group_count, batch):
                        # Collapse objects from our current index through index+batch size, add the result to meshes[]
                        mesh = collapse_objects(group[x:(x + batch)])
                        if mesh is not None:
                            meshes.append(mesh)

                    collapse_objects(meshes)

                elif group_count > 1:
                    collapse_objects(group)

                objs_processed += group_count

                if objs_processed >= milestone_collapse:
                    print("%d%%  -  Collapsing..." % (
                        round((objs_processed * 100) / num_unique_objs)
                    ))
                    milestone_collapse = min(num_unique_objs, objs_processed + (num_unique_objs / 100))

            print("Collapsing Done")

            # If an object is an instance, add a number rather than collapsing
            for i, group in enumerate(instances_sorted.values()):
                group_count = len(group)

                # Padding to 3 digits is preferred, but this automatically adapts if the object count requires it
                digits = magnitude_of_number(group_count)

                for i2, obj in enumerate(group):
                    # Format for 0 padded digit
                    obj.name = u"%s - %s" % (obj.name, str(i2).zfill(max(3, digits)))

                instances_processed += group_count

                if instances_processed >= milestone_naming:
                    print("%d%%  -  Renaming..." % (
                        round((100 * instances_processed) / num_instances)
                    ))
                    milestone_naming = min(num_instances, instances_processed + (num_instances / 100))

            print("Naming Done")

            print("Collapsed %d Meshes into %d" % (total_objs, len(unique_objs_sorted.keys()) + num_instances))
            return

        # Catches any exceptions thrown while collapsing objects and prints the traceback
        except Exception as ex:
            print("Error: %s\n The script must now exit" % ex)
            traceback.print_exc()
            return


# try:
#     run()
# except Exception as e:
#     print(e)

run()
