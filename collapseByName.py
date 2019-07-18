# Collapse By Name v1.0
# Authored by Josh Hollander and Avery Brown
#
# Gathers all objects in the scene, grouping them by name.  Objects with the exact same name will be merged together.
# Useful for consolidating Revit models.
#
# Inspiration for part of this code comes from ScriptSpot user antomor, and his Quick Attach MAXScript.

# Import PyMXS, MaxPlus, and set up shorthand vars
import pymxs
import MaxPlus
import traceback

maxscript = MaxPlus.Core.EvalMAXScript
rt = pymxs.runtime


# ==================================================
#                    Functions
# ==================================================

def collapse_objects(obj_list):
    # NOTE: This function will cause 3ds Max to crash if it's passed a list of length 1.  I have no idea why.
    # First make sure we weren't passed an empty list
    if not obj_list:
        return None

    # DEBUG
    # print len(obj_list)

    # Next make sure we weren't passed a list with only one object.  For reasons unknown to me, this will crash Max.
    if len(obj_list) == 1:
        return obj_list[0]

    # Create an empty Editable Mesh object to attach to
    root = rt.Editable_Mesh()
    root.name = obj_list[0].name

    # Make sure the object is attachable, then attach it to root
    for obj in obj_list:
        if rt.SuperClassOf(obj) == rt.GeometryClass and rt.IsValidNode(obj):
            rt.meshop.attach(root, obj, condenseMat=True, deleteSourceNode=True, attachMat=rt.name("IDToMat"))

    return root


def run():

    # ==================================================
    #                 Collect Objects
    # ==================================================

    objs = rt.objects

    # DEBUG - Use Selection
    # objs = rt.getCurrentSelection()

    objs_count = len(objs)
    milestone = (objs_count / 20)
    objs_sorted = {}

    # Iterate over all objects, sorting them into groups by name
    print 'Examining %d Scene Objects...' % objs_count
    for i, obj in enumerate(objs):
        try:
            objs_sorted[obj.name].append(obj)

        except Exception:
            objs_sorted[obj.name] = []
            objs_sorted[obj.name].append(obj)

        finally:
            if i > milestone:
                print "%d%%" % ((i*100)/objs_count)
                milestone = milestone + (objs_count / 20)

    # ==================================================
    #                 Collapse Groups
    # ==================================================

    print "Collapsing Objects..."

    with pymxs.undo(False), pymxs.redraw(False):
        try:
            batch = 25
            objs_processed = 0

            for group in objs_sorted.values():
                print "%d%%  -  Collapsing %s" % (min(100, ((100*objs_processed) / objs_count)), group[0].name)
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
                rt.gc()

            print "Collapsed %d Meshes into %d" % (objs_count, len(objs_sorted.keys()))
            return

        except Exception as e:
            traceback.print_exc()
            return


run()
