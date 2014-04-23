#!/usr/bin/env python

"""@namespace IMP.pmi.analysis
   Analysis tools.
"""

import IMP
import IMP.algebra


class Alignment():

    """
    This class performs alignment and RMSD calculation for two sets of coordinates

    Inputs:

      - query = {'p1':coords(L,3), 'p2':coords(L,3)}
      - template = {'p1':coords(L,3), 'p2':coords(L,3)}

    The class also takes into accout non-equal stoichiometry of the proteins. If this
    is the case, the protein names of protein in multiple copies should be delivered
    in the following form: nameA..1, nameA..2 (note two dots).
    """

    def __init__(self, template, query):

        global array, argwhere, mgrid, shape, reshape, zeros, diagonal, argsort, deepcopy, cdist, sqrt
        global product, permutations
        from numpy import array, argwhere, mgrid, shape, reshape, zeros, diagonal, argsort
        from copy import deepcopy
        from scipy.spatial.distance import cdist
        from math import sqrt
        from itertools import permutations, product

        self.query = query
        self.template = template

        if len(self.query.keys()) != len(self.template.keys()):
            print '''ERROR: the number of proteins
                               in template and query does not match!'''
            exit()

    def permute(self):

        self.proteins = sorted(self.query.keys())
        prots_uniq = [i.split('..')[0] for i in self.proteins]
        P = {}
        for p in prots_uniq:
            np = prots_uniq.count(p)
            copies = [i for i in self.proteins if i.split('..')[0] == p]
            prmts = list(permutations(copies, len(copies)))
            P[p] = prmts
        self.P = P
        self.Product = list(product(*P.values()))

    def get_rmsd(self):

        self.permute()

        template_xyz = []
        torder = sum([list(i) for i in self.Product[0]], [])
        for t in torder:
            template_xyz += [i for i in self.template[t]]
        template_xyz = array(template_xyz)

        self.rmsd = 10000000000.
        for comb in self.Product:
            order = sum([list(i) for i in comb], [])
            query_xyz = []
            for p in order:
                query_xyz += [i for i in self.query[p]]
            query_xyz = array(query_xyz)
            if len(template_xyz) != len(query_xyz):
                print '''Alignment.get_rmsd: ERROR: the number of coordinates
                               in template and query does not match!'''
                exit()
            dist = sqrt(
                sum(diagonal(cdist(template_xyz, query_xyz) ** 2)) / len(template_xyz))
            if dist < self.rmsd:
                self.rmsd = dist
        return self.rmsd

    def align(self):

        self.permute()

        template_xyz = []
        torder = sum([list(i) for i in self.Product[0]], [])
        for t in torder:
            template_xyz += [IMP.algebra.Vector3D(i) for i in self.template[t]]
        #template_xyz = array(template_xyz)

        self.rmsd, Transformation = 10000000000., ''
        for comb in self.Product:
            order = sum([list(i) for i in comb], [])
            query_xyz = []
            for p in order:
                query_xyz += [IMP.algebra.Vector3D(i) for i in self.query[p]]
            #query_xyz = array(query_xyz)

            if len(template_xyz) != len(query_xyz):
                print '''ERROR: the number of coordinates
                               in template and query does not match!'''
                exit()

            transformation = IMP.algebra.get_transformation_aligning_first_to_second(
                query_xyz,
                template_xyz)
            query_xyz_tr = [transformation.get_transformed(n)
                            for n in query_xyz]

            dist = sqrt(
                sum(diagonal(cdist(template_xyz, query_xyz_tr) ** 2)) / len(template_xyz))
            if dist < self.rmsd:
                self.rmsd = dist
                Transformation = transformation

        return (self.rmsd, Transformation)


# TEST for the alignment ###
"""
import numpy as np
Proteins = {'a..1':np.array([np.array([-1.,1.])]),
            'a..2':np.array([np.array([1.,1.,])]),
            'a..3':np.array([np.array([-2.,1.])]),
            'b':np.array([np.array([0.,-1.])]),
            'c..1':np.array([np.array([-1.,-1.])]),
            'c..2':np.array([np.array([1.,-1.])]),
            'd':np.array([np.array([0.,0.])]),
            'e':np.array([np.array([0.,1.])])}

Ali = Alignment(Proteins, Proteins)
Ali.permute()
if Ali.get_rmsd() == 0.0: print 'successful test!'
else: print 'ERROR!'; exit()
"""


# ----------------------------------
class Violations():

    def __init__(self, filename):
        global impem, deepcopy, cdist, array, argwhere, mgrid, shape, reshape, zeros, sqrt, diagonal, argsort
        import IMP.em as impem
        from numpy import array, argwhere, mgrid, shape, reshape, zeros, diagonal, argsort
        from copy import deepcopy
        from scipy.spatial.distance import cdist
        from math import sqrt
        self.violation_thresholds = {}
        self.violation_counts = {}

        data = open(filename)
        D = data.readlines()
        data.close()

        for d in D:
            d = d.strip().split()
            self.violation_thresholds[d[0]] = float(d[1])

    def get_number_violated_restraints(self, rsts_dict):
        num_violated = 0
        for rst in self.violation_thresholds:
            if rst not in rsts_dict:
                continue  # print rst;
            if float(rsts_dict[rst]) > self.violation_thresholds[rst]:
                num_violated += 1
                if rst not in self.violation_counts:
                    self.violation_counts[rst] = 1
                else:
                    self.violation_counts[rst] += 1
        return num_violated


# ----------------------------------
class Clustering():

    def __init__(self):

        global impem, deepcopy, cdist, array, argwhere, mgrid, shape, reshape, zeros, sqrt, diagonal, argsort, npsum
        import IMP.em as impem
        from numpy import array, argwhere, mgrid, shape, reshape, zeros, diagonal, argsort
        from numpy import sum as npsum
        from copy import deepcopy
        from scipy.spatial.distance import cdist
        from math import sqrt
        self.all_coords = {}
        self.structure_cluster_ids = None
        self.tmpl_coords = None

    def set_template(self, part_coords):

        self.tmpl_coords = part_coords

    def fill(self, frame, Coords):
        """
        fill stores coordinates of a model into a dictionary all_coords,
        containint coordinates for all models.
        """

        self.all_coords[frame] = Coords

    def dist_matrix(self, is_mpi=False):
        from itertools import combinations

        if is_mpi:
            from mpi4py import MPI
            comm = MPI.COMM_WORLD
            rank = comm.Get_rank()
            number_of_processes = comm.size
        else:
            number_of_processes = 1
            rank = 0

        self.model_list_names = self.all_coords.keys()
        self.model_indexes = range(len(self.model_list_names))
        self.model_indexes_dict = dict(
            zip(self.model_list_names, self.model_indexes))
        model_indexes_unique_pairs = list(combinations(self.model_indexes, 2))

        my_model_indexes_unique_pairs = IMP.pmi.tools.chunk_list_into_segments(
            model_indexes_unique_pairs,
            number_of_processes)[rank]

        print "process %s assigned with %s pairs" % (str(rank), str(len(my_model_indexes_unique_pairs)))

        (raw_distance_dict, self.transformation_distance_dict) = self.matrix_calculation(self.all_coords,
                                                                                         self.tmpl_coords,
                                                                                         my_model_indexes_unique_pairs)

        if number_of_processes > 1:
            raw_distance_dict = IMP.pmi.tools.scatter_and_gather(
                raw_distance_dict)
            pickable_transformations = self.get_pickable_transformation_distance_dict(
            )
            pickable_transformations = IMP.pmi.tools.scatter_and_gather(
                pickable_transformations)
            self.set_transformation_distance_dict_from_pickable(
                pickable_transformations)

        self.raw_distance_matrix = zeros(
            (len(self.model_list_names), len(self.model_list_names)))
        for item in raw_distance_dict:
            (f1, f2) = item
            self.raw_distance_matrix[f1, f2] = raw_distance_dict[item]
            self.raw_distance_matrix[f2, f1] = raw_distance_dict[item]

    def do_cluster(self, number_of_clusters):
        from sklearn.cluster import KMeans
        kmeans = KMeans(n_clusters=number_of_clusters)
        kmeans.fit_predict(self.raw_distance_matrix)

        self.structure_cluster_ids = kmeans.labels_

    def get_pickable_transformation_distance_dict(self):
        pickable_transformations = {}
        for label in self.transformation_distance_dict:
            tr = self.transformation_distance_dict[label]
            trans = tuple(tr.get_translation())
            rot = tuple(tr.get_rotation().get_quaternion())
            pickable_transformations[label] = (rot, trans)
        return pickable_transformations

    def set_transformation_distance_dict_from_pickable(
        self,
            pickable_transformations):
        self.transformation_distance_dict = {}
        for label in pickable_transformations:
            tr = pickable_transformations[label]
            trans = IMP.algebra.Vector3D(tr[1])
            rot = IMP.algebra.Rotation3D(tr[0])
            self.transformation_distance_dict[
                label] = IMP.algebra.Transformation3D(rot, trans)

    def save_distance_matrix_file(self, file_name='cluster.rawmatrix.pkl'):
        import pickle
        import numpy as np
        outf = open(file_name + ".data", 'w')

        # to pickle the transformation dictionary
        # you have to save the arrays correposnding to
        # the transformations

        pickable_transformations = self.get_pickable_transformation_distance_dict(
        )
        pickle.dump(
            (self.structure_cluster_ids,
             self.model_list_names,
             pickable_transformations),
            outf)

        np.save(file_name + ".npy", self.raw_distance_matrix)

    def load_distance_matrix_file(self, file_name='cluster.rawmatrix.pkl'):
        import pickle
        import numpy as np

        inputf = open(file_name + ".data", 'r')
        (self.structure_cluster_ids, self.model_list_names,
         pickable_transformations) = pickle.load(inputf)
        inputf.close()

        self.raw_distance_matrix = np.load(file_name + ".npy")

        self.set_transformation_distance_dict_from_pickable(
            pickable_transformations)
        self.model_indexes = range(len(self.model_list_names))
        self.model_indexes_dict = dict(
            zip(self.model_list_names, self.model_indexes))

    def plot_matrix(self, figurename="clustermatrix.png"):
        import pylab as pl
        from scipy.cluster import hierarchy as hrc

        fig = pl.figure()
        ax = fig.add_subplot(211)
        dendrogram = hrc.dendrogram(
            hrc.linkage(self.raw_distance_matrix),
            color_threshold=7,
            no_labels=True)
        leaves_order = dendrogram['leaves']

        ax = fig.add_subplot(212)
        cax = ax.imshow(
            self.raw_distance_matrix[leaves_order,
                                     :][:,
                                        leaves_order],
            interpolation='nearest')
        # ax.set_yticks(range(len(self.model_list_names)))
        #ax.set_yticklabels( [self.model_list_names[i] for i in leaves_order] )
        fig.colorbar(cax)
        pl.savefig(figurename, dpi=300)
        pl.show()

    def get_model_index_from_name(self, name):
        return self.model_indexes_dict[name]

    def get_cluster_labels(self):
        # this list
        return list(set(self.structure_cluster_ids))

    def get_number_of_clusters(self):
        return len(self.get_cluster_labels())

    def get_cluster_label_indexes(self, label):
        return (
            [i for i, l in enumerate(self.structure_cluster_ids) if l == label]
        )

    def get_cluster_label_names(self, label):
        return (
            [self.model_list_names[i]
                for i in self.get_cluster_label_indexes(label)]
        )

    def get_cluster_label_average_rmsd(self, label):

        indexes = self.get_cluster_label_indexes(label)

        if len(indexes) > 1:
            sub_distance_matrix = self.raw_distance_matrix[
                indexes, :][:, indexes]
            average_rmsd = npsum(sub_distance_matrix) / \
                (len(sub_distance_matrix)
                 ** 2 - len(sub_distance_matrix))
        else:
            average_rmsd = 0.0
        return average_rmsd

    def get_cluster_label_size(self, label):
        return len(self.get_cluster_label_indexes(label))

    def get_transformation_to_first_member(
        self,
        cluster_label,
            structure_index):
        reference = self.get_cluster_label_indexes(cluster_label)[0]
        return self.transformation_distance_dict[(reference, structure_index)]

    def matrix_calculation(self, all_coords, template_coords, list_of_pairs):

        import IMP
        import IMP.pmi
        import IMP.pmi.analysis

        model_list_names = all_coords.keys()
        rmsd_protein_names = all_coords[model_list_names[0]].keys()
        raw_distance_dict = {}
        transformation_distance_dict = {}
        if template_coords is None:
            do_alignment = False
        else:
            do_alignment = True
            alignment_template_protein_names = template_coords.keys()

        for (f1, f2) in list_of_pairs:

            if not do_alignment:
                # here we only get the rmsd,
                # we need that for instance when you want to cluster conformations
                # globally, eg the EM map is a reference
                transformation = IMP.algebra.get_identity_transformation_3d()

                coords_f1 = dict([(pr, all_coords[model_list_names[f1]][pr])
                                 for pr in rmsd_protein_names])
                coords_f2 = {}
                for pr in rmsd_protein_names:
                    coords_f2[pr] = all_coords[model_list_names[f2]][pr]

                Ali = IMP.pmi.analysis.Alignment(coords_f1, coords_f2)
                rmsd = Ali.get_rmsd()

            elif do_alignment:
                # here we actually align the conformations first
                # and than calculate the rmsd. We need that when the
                # protein(s) is the reference
                coords_f1 = dict([(pr, all_coords[model_list_names[f1]][pr])
                                 for pr in alignment_template_protein_names])
                coords_f2 = dict([(pr, all_coords[model_list_names[f2]][pr])
                                 for pr in alignment_template_protein_names])

                Ali = IMP.pmi.analysis.Alignment(coords_f1, coords_f2)
                template_rmsd, transformation = Ali.align()

                # here we calculate the rmsd
                # we will align two models based n the nuber of subunits provided
                # and transform coordinates of model 2 to model 1
                coords_f1 = dict([(pr, all_coords[model_list_names[f1]][pr])
                                 for pr in rmsd_protein_names])
                coords_f2 = {}
                for pr in rmsd_protein_names:
                    coords_f2[pr] = [transformation.get_transformed(
                        i) for i in all_coords[model_list_names[f2]][pr]]

                Ali = IMP.pmi.analysis.Alignment(coords_f1, coords_f2)
                rmsd = Ali.get_rmsd()

            raw_distance_dict[(f1, f2)] = rmsd
            raw_distance_dict[(f2, f1)] = rmsd
            transformation_distance_dict[(f1, f2)] = transformation
            transformation_distance_dict[(f2, f1)] = transformation

        return raw_distance_dict, transformation_distance_dict


# ----------------------------------

class GetModelDensity():

    def __init__(self, custom_ranges, representation=None, voxel=5.0):
        '''
        custom_ranges ={'kin28':[['kin28',1,-1]],
                'density_name_1' :[('ccl1')],
                'density_name_2' :[(1,142,'tfb3d1'),(143,700,'tfb3d2')],


        '''
        global impem
        import IMP.em as impem

        self.representation = representation
        self.voxel = voxel
        self.densities = {}
        self.count_models = 0.0
        self.custom_ranges = custom_ranges

    def add_subunits_density(self, hierarchy=None):
            # the hierarchy is optional, if passed
        self.count_models += 1.0
        for density_name in self.custom_ranges:
            parts = []
            if hierarchy:
                all_particles_by_segments = []

            for seg in self.custom_ranges[density_name]:
                if not hierarchy:
                    parts += IMP.tools.select_by_tuple(self.representation,
                                                       seg, resolution=1, name_is_ambiguous=False)
                else:

                    if type(seg) == str:
                        children = [
                            child for child in hierarchy.get_children(
                            ) if child.get_name(
                            ) == seg]
                        s = IMP.atom.Selection(children)
                    if type(seg) == tuple:
                        children = [
                            child for child in hierarchy.get_children(
                            ) if child.get_name(
                            ) == seg[
                                2]]
                        s = IMP.atom.Selection(
                            children, residue_indexes=range(seg[0], seg[1] + 1))
                    all_particles_by_segments += s.get_selected_particles()

            if hierarchy:
                part_dict = get_particles_at_resolution_one(hierarchy)
                all_particles_by_resolution = []
                for name in part_dict:
                    all_particles_by_resolution += part_dict[name]
                parts = list(
                    set(all_particles_by_segments) & set(all_particles_by_resolution))

            self.create_density_from_particles(parts, density_name)

    def normalize_density(self):
        pass

    def create_density_from_particles(self, ps, name,
                                      resolution=1,
                                      kernel_type='GAUSSIAN'):
        '''pass XYZR particles with mass and create a density from them.
        kernel type options are GAUSSIAN, BINARIZED_SPHERE, and SPHERE.'''

        kd = {
            'GAUSSIAN': IMP.em.GAUSSIAN,
            'BINARIZED_SPHERE': IMP.em.BINARIZED_SPHERE,
            'SPHERE': IMP.em.SPHERE}

        dmap = impem.SampledDensityMap(ps, resolution, self.voxel)
        dmap.calcRMS()
        if name not in self.densities:
            self.densities[name] = dmap
        else:
            self.densities[name].add(dmap)

    def write_mrc(self, path="./"):

        for density_name in self.densities:
            self.densities[density_name].multiply(1. / self.count_models)
            impem.write_map(
                self.densities[density_name],
                path + "/" + density_name + ".mrc",
                impem.MRCReaderWriter())

# ----------------------------------


class GetContactMap():

    def __init__(self, distance=15.):
        global impem, deepcopy, cdist, array, argwhere, mgrid, shape, reshape, zeros, sqrt, diagonal, argsort, log
        import IMP.em as impem
        from numpy import array, argwhere, mgrid, shape, reshape, zeros, diagonal, argsort, log
        from copy import deepcopy
        from scipy.spatial.distance import cdist
        global itemgetter
        from operator import itemgetter

        self.distance = distance
        self.contactmap = ''
        self.namelist = []
        self.xlinks = 0
        self.XL = {}
        self.expanded = {}
        self.resmap = {}

    def set_prot(self, prot):
        import IMP.pmi.tools
        self.prot = prot
        self.protnames = []
        coords = []
        radii = []
        namelist = []

        particles_dictionary = get_particles_at_resolution_one(self.prot)

        for name in particles_dictionary:
            residue_indexes = []
            for p in particles_dictionary[name]:
                print p.get_name()
                residue_indexes += IMP.pmi.tools.get_residue_indexes(p)
                #residue_indexes.add( )

            if len(residue_indexes) != 0:
                self.protnames.append(name)
                for res in range(min(residue_indexes), max(residue_indexes) + 1):
                    d = IMP.core.XYZR(p)
                    new_name = name + ":" + str(res)
                    if name not in self.resmap:
                        self.resmap[name] = {}
                    if res not in self.resmap:
                        self.resmap[name][res] = {}

                    self.resmap[name][res] = new_name
                    namelist.append(new_name)

                    crd = array([d.get_x(), d.get_y(), d.get_z()])
                    coords.append(crd)
                    radii.append(d.get_radius())

        coords = array(coords)
        radii = array(radii)

        if len(self.namelist) == 0:
            self.namelist = namelist
            self.contactmap = zeros((len(coords), len(coords)))

        distances = cdist(coords, coords)
        distances = (distances - radii).T - radii
        distances = distances <= self.distance

        print coords
        print radii
        print distances

        self.contactmap += distances

    def get_subunit_coords(self, frame, align=0):
        coords = []
        radii = []
        namelist = []
        test, testr = [], []
        for part in self.prot.get_children():
            SortedSegments = []
            print part
            for chl in part.get_children():
                start = IMP.atom.get_leaves(chl)[0]
                end = IMP.atom.get_leaves(chl)[-1]

                startres = IMP.atom.Fragment(start).get_residue_indexes()[0]
                endres = IMP.atom.Fragment(end).get_residue_indexes()[-1]
                SortedSegments.append((chl, startres))
            SortedSegments = sorted(SortedSegments, key=itemgetter(1))

            for sgmnt in SortedSegments:
                for leaf in IMP.atom.get_leaves(sgmnt[0]):
                    p = IMP.core.XYZR(leaf)
                    crd = array([p.get_x(), p.get_y(), p.get_z()])

                    coords.append(crd)
                    radii.append(p.get_radius())

                    new_name = part.get_name() + '_' + sgmnt[0].get_name() +\
                        '_' + \
                        str(IMP.atom.Fragment(leaf)
                            .get_residue_indexes()[0])
                    namelist.append(new_name)
                    self.expanded[new_name] = len(
                        IMP.atom.Fragment(leaf).get_residue_indexes())
                    if part.get_name() not in self.resmap:
                        self.resmap[part.get_name()] = {}
                    for res in IMP.atom.Fragment(leaf).get_residue_indexes():
                        self.resmap[part.get_name()][res] = new_name

        coords = array(coords)
        radii = array(radii)
        if len(self.namelist) == 0:
            self.namelist = namelist
            self.contactmap = zeros((len(coords), len(coords)))
        distances = cdist(coords, coords)
        distances = (distances - radii).T - radii
        distances = distances <= self.distance
        self.contactmap += distances

    def add_xlinks(
        self,
        filname,
            identification_string='ISDCrossLinkMS_Distance_'):
        # 'ISDCrossLinkMS_Distance_interrb_6629-State:0-20:RPS30_218:eIF3j-1-1-0.1_None'
        self.xlinks = 1
        data = open(filname)
        D = data.readlines()
        data.close()

        for d in D:
            if identification_string in d:
                d = d.replace(
                    "_",
                    " ").replace("-",
                                 " ").replace(":",
                                              " ").split()

                t1, t2 = (d[0], d[1]), (d[1], d[0])
                if t1 not in self.XL:
                    self.XL[t1] = [(int(d[2]) + 1, int(d[3]) + 1)]
                    self.XL[t2] = [(int(d[3]) + 1, int(d[2]) + 1)]
                else:
                    self.XL[t1].append((int(d[2]) + 1, int(d[3]) + 1))
                    self.XL[t2].append((int(d[3]) + 1, int(d[2]) + 1))

    def dist_matrix(self, skip_cmap=0, skip_xl=1):
        K = self.namelist
        M = self.contactmap
        C, R = [], []
        L = sum(self.expanded.values())
        proteins = self.protnames

        # exp new
        if skip_cmap == 0:
            Matrices = {}
            proteins = [p.get_name() for p in self.prot.get_children()]
            missing = []
            for p1 in xrange(len(proteins)):
                for p2 in xrange(p1, len(proteins)):
                    pl1, pl2 = max(
                        self.resmap[proteins[p1]].keys()), max(self.resmap[proteins[p2]].keys())
                    pn1, pn2 = proteins[p1], proteins[p2]
                    mtr = zeros((pl1 + 1, pl2 + 1))
                    print 'Creating matrix for: ', p1, p2, pn1, pn2, mtr.shape, pl1, pl2
                    for i1 in xrange(1, pl1 + 1):
                        for i2 in xrange(1, pl2 + 1):
                            try:
                                r1 = K.index(self.resmap[pn1][i1])
                                r2 = K.index(self.resmap[pn2][i2])
                                r = M[r1, r2]
                                mtr[i1 - 1, i2 - 1] = r
                            except KeyError:
                                missing.append((pn1, pn2, i1, i2))
                                pass
                    Matrices[(pn1, pn2)] = mtr

        # add cross-links
        if skip_xl == 0:
            if self.XL == {}:
                print "ERROR: cross-links were not provided, use add_xlinks function!"
                exit()
            Matrices_xl = {}
            missing_xl = []
            for p1 in xrange(len(proteins)):
                for p2 in xrange(p1, len(proteins)):
                    pl1, pl2 = max(
                        self.resmap[proteins[p1]].keys()), max(self.resmap[proteins[p2]].keys())
                    pn1, pn2 = proteins[p1], proteins[p2]
                    mtr = zeros((pl1 + 1, pl2 + 1))
                    flg = 0
                    try:
                        xls = self.XL[(pn1, pn2)]
                    except KeyError:
                        try:
                            xls = self.XL[(pn2, pn1)]
                            flg = 1
                        except KeyError:
                            flg = 2
                    if flg == 0:
                        print 'Creating matrix for: ', p1, p2, pn1, pn2, mtr.shape, pl1, pl2
                        for xl1, xl2 in xls:
                            if xl1 > pl1:
                                print 'X' * 10, xl1, xl2
                                xl1 = pl1
                            if xl2 > pl2:
                                print 'X' * 10, xl1, xl2
                                xl2 = pl2
                            mtr[xl1 - 1, xl2 - 1] = 100
                    elif flg == 1:
                        print 'Creating matrix for: ', p1, p2, pn1, pn2, mtr.shape, pl1, pl2
                        for xl1, xl2 in xls:
                            if xl1 > pl1:
                                print 'X' * 10, xl1, xl2
                                xl1 = pl1
                            if xl2 > pl2:
                                print 'X' * 10, xl1, xl2
                                xl2 = pl2
                            mtr[xl2 - 1, xl1 - 1] = 100
                    else:
                        print 'WTF!'
                        exit()
                    Matrices_xl[(pn1, pn2)] = mtr

        # expand the matrix to individual residues
        #NewM = []
        # for x1 in xrange(len(K)):
        #    lst = []
        #    for x2 in xrange(len(K)):
        #        lst += [M[x1,x2]]*self.expanded[K[x2]]
        #    for i in xrange(self.expanded[K[x1]]): NewM.append(array(lst))
        #NewM = array(NewM)

        # make list of protein names and create coordinate lists
        C = proteins
        # W is the component length list,
        # R is the contiguous coordinates list
        W, R = [], []
        for i, c in enumerate(C):
            cl = max(self.resmap[c].keys())
            W.append(cl)
            if i == 0:
                R.append(cl)
            else:
                R.append(R[-1] + cl)

        # start plotting
        import matplotlib.pyplot as plt
        import matplotlib.gridspec as gridspec
        import scipy.sparse as sparse

        f = plt.figure()
        gs = gridspec.GridSpec(len(W), len(W),
                               width_ratios=W,
                               height_ratios=W)

        cnt = 0
        for x1, r1 in enumerate(R):
            if x1 == 0:
                s1 = 0
            else:
                s1 = R[x1 - 1]
            for x2, r2 in enumerate(R):
                if x2 == 0:
                    s2 = 0
                else:
                    s2 = R[x2 - 1]

                ax = plt.subplot(gs[cnt])
                if skip_cmap == 0:
                    try:
                        mtr = Matrices[(C[x1], C[x2])]
                    except KeyError:
                        mtr = Matrices[(C[x2], C[x1])].T
                    #cax = ax.imshow(log(NewM[s1:r1,s2:r2] / 1.), interpolation='nearest', vmin=0., vmax=log(NewM.max()))
                    cax = ax.imshow(
                        log(mtr),
                        interpolation='nearest',
                        vmin=0.,
                        vmax=log(NewM.max()))
                    ax.set_xticks([])
                    ax.set_yticks([])
                if skip_xl == 0:
                    try:
                        mtr = Matrices_xl[(C[x1], C[x2])]
                    except KeyError:
                        mtr = Matrices_xl[(C[x2], C[x1])].T
                    cax = ax.spy(
                        sparse.csr_matrix(mtr),
                        markersize=10,
                        color='white',
                        linewidth=100,
                        alpha=0.5)
                    ax.set_xticks([])
                    ax.set_yticks([])

                cnt += 1
                if x2 == 0:
                    ax.set_ylabel(C[x1], rotation=90)
        plt.show()


# ------------------------------------------------------------------

class CrossLinkTable():

    def __init__(self):
        self.crosslinks = []
        self.external_csv_data = None
        self.crosslinkedprots = set()
        self.mindist = +10000000.0
        self.maxdist = -10000000.0
        self.contactmap = None

    def set_hierarchy(self, prot):
        import IMP.pmi.tools
        self.prot_length_dict = {}

        for i in prot.get_children():
            name = i.get_name()
            residue_indexes = []
            for p in IMP.atom.get_leaves(i):
                residue_indexes += IMP.pmi.tools.get_residue_indexes(p)

            if len(residue_indexes) != 0:
                self.prot_length_dict[name] = max(residue_indexes)

    def set_coordinates_for_contact_map(self, prot):
        from numpy import zeros, array, where
        from scipy.spatial.distance import cdist

        coords = []
        radii = []
        namelist = []

        particles_dictionary = get_particles_at_resolution_one(prot)

        resindex = 0
        self.index_dictionary = {}

        for name in particles_dictionary:
            residue_indexes = []
            for p in particles_dictionary[name]:
                print p.get_name()
                residue_indexes = IMP.pmi.tools.get_residue_indexes(p)
                #residue_indexes.add( )

                if len(residue_indexes) != 0:

                    for res in range(min(residue_indexes), max(residue_indexes) + 1):
                        d = IMP.core.XYZR(p)

                        crd = array([d.get_x(), d.get_y(), d.get_z()])
                        coords.append(crd)
                        radii.append(d.get_radius())
                        if name not in self.index_dictionary:
                            self.index_dictionary[name] = [resindex]
                        else:
                            self.index_dictionary[name].append(resindex)
                        resindex += 1

        coords = array(coords)
        radii = array(radii)

        distances = cdist(coords, coords)
        distances = (distances - radii).T - radii

        distances = where(distances <= 20.0, 1.0, 0)
        if self.contactmap is None:
            self.contactmap = zeros((len(coords), len(coords)))
        self.contactmap += distances

    def set_crosslinks(
        self, data_file, search_label='ISDCrossLinkMS_Distance_',
        mapping=None,
        external_csv_data_file=None,
            external_csv_data_file_unique_id_key="Unique ID"):

        # example key ISDCrossLinkMS_Distance_intrarb_937-State:0-108:RPS3_55:RPS30-1-1-0.1_None
        # mapping is a dictionary that maps standard keywords to entry positions in the key string
        # confidence class is a filter that
        # external datafile is a datafile that contains further information on the crosslinks
        # it will use the unique id to create the dictionary keys

        import IMP.pmi.output
        import numpy as np

        po = IMP.pmi.output.ProcessOutput(data_file)
        keys = po.get_keys()
        xl_keys = [k for k in keys if search_label in k]
        fs = po.get_fields(xl_keys)

        # this dictionary stores the occurency of given crosslinks
        self.cross_link_frequency = {}

        # this dictionary stores the series of distances for given crosslinked
        # residues
        self.cross_link_distances = {}

        # this dictionary stores the series of distances for given crosslinked
        # residues
        self.cross_link_distances_unique = {}

        if not external_csv_data_file is None:
            # this dictionary stores the further information on crosslinks
            # labeled by unique ID
            self.external_csv_data = {}
            xldb = IMP.pmi.tools.get_db_from_csv(external_csv_data_file)

            for xl in xldb:
                self.external_csv_data[
                    xl[external_csv_data_file_unique_id_key]] = xl

        # this list keeps track the tuple of cross-links and sample
        # so that we don't count twice the same crosslinked residues in the
        # same sample
        cross_link_frequency_list = []

        self.unique_cross_link_list = []

        for key in fs:
            print key
            keysplit = key.replace(
                "_",
                " ").replace(
                "-",
                " ").replace(
                ":",
                " ").split(
            )
            if mapping is None:
                r1 = int(keysplit[5])
                c1 = keysplit[6]
                r2 = int(keysplit[7])
                c2 = keysplit[8]
                try:
                    confidence = keysplit[12]
                except:
                    confidence = '0.0'
                try:
                    unique_identifier = keysplit[3]
                except:
                    unique_identifier = '0'
            else:
                r1 = int(keysplit[mapping["Residue1"]])
                c1 = keysplit[mapping["Protein1"]]
                r2 = int(keysplit[mapping["Residue2"]])
                c2 = keysplit[mapping["Protein2"]]
                try:
                    confidence = keysplit[mapping["Confidence"]]
                except:
                    confidence = '0.0'
                try:
                    unique_identifier = keysplit[mapping["Unique Identifier"]]
                except:
                    unique_identifier = '0'

            self.crosslinkedprots.add(c1)
            self.crosslinkedprots.add(c2)

            # check if the input confidence class corresponds to the
            # one of the cross-link

            dists = map(float, fs[key])
            mdist = self.median(dists)

            stdv = np.std(np.array(dists))
            if self.mindist > mdist:
                self.mindist = mdist
            if self.maxdist < mdist:
                self.maxdist = mdist

            # calculate the frequency of unique crosslinks within the same
            # sample
            if not self.external_csv_data is None:
                sample = self.external_csv_data[unique_identifier]["Sample"]
            else:
                sample = "None"

            if (r1, c1, r2, c2, sample) not in cross_link_frequency_list:
                if (r1, c1, r2, c2) not in self.cross_link_frequency:
                    self.cross_link_frequency[(r1, c1, r2, c2)] = 1
                    self.cross_link_frequency[(r2, c2, r1, c1)] = 1
                else:
                    self.cross_link_frequency[(r2, c2, r1, c1)] += 1
                    self.cross_link_frequency[(r1, c1, r2, c2)] += 1
                cross_link_frequency_list.append((r1, c1, r2, c2, sample))
                cross_link_frequency_list.append((r2, c2, r1, c1, sample))
                self.unique_cross_link_list.append(
                    (r1, c1, r2, c2, sample, mdist))

            if (r1, c1, r2, c2) not in self.cross_link_distances:
                self.cross_link_distances[(
                    r1,
                    c1,
                    r2,
                    c2,
                    mdist,
                    confidence)] = dists
                self.cross_link_distances[(
                    r2,
                    c2,
                    r1,
                    c1,
                    mdist,
                    confidence)] = dists
                self.cross_link_distances_unique[(r1, c1, r2, c2)] = dists
            else:
                self.cross_link_distances[(
                    r2,
                    c2,
                    r1,
                    c1,
                    mdist,
                    confidence)] += dists
                self.cross_link_distances[(
                    r1,
                    c1,
                    r2,
                    c2,
                    mdist,
                    confidence)] += dists

            self.crosslinks.append(
                (r1,
                 c1,
                 r2,
                 c2,
                 mdist,
                 stdv,
                 confidence,
                 unique_identifier,
                 'original'))
            self.crosslinks.append(
                (r2,
                 c2,
                 r1,
                 c1,
                 mdist,
                 stdv,
                 confidence,
                 unique_identifier,
                 'reversed'))

        self.cross_link_frequency_inverted = {}
        for xl in self.unique_cross_link_list:
            (r1, c1, r2, c2, sample, mdist) = xl
            frequency = self.cross_link_frequency[(r1, c1, r2, c2)]
            if frequency not in self.cross_link_frequency_inverted:
                self.cross_link_frequency_inverted[
                    frequency] = [(r1, c1, r2, c2, sample)]
            else:
                self.cross_link_frequency_inverted[
                    frequency].append((r1, c1, r2, c2, sample))

        # -------------

    def median(self, mylist):
        sorts = sorted(mylist)
        length = len(sorts)
        if not length % 2:
            return (sorts[length / 2] + sorts[length / 2 - 1]) / 2.0
        return sorts[length / 2]

    def colormap(self, dist, threshold=35, tolerance=0):
        if dist < threshold - tolerance:
            return "Green"
        elif dist >= threshold + tolerance:
            return "Orange"
        else:
            return "Orange"

    def write_cross_link_database(self, filename, format='csv'):
        import csv

        fieldnames = [
            "Unique ID", "Protein1", "Residue1", "Protein2", "Residue2",
            "Median Distance", "Standard Deviation", "Confidence", "Frequency", "Arrangement"]

        if not self.external_csv_data is None:
            keys = self.external_csv_data.keys()
            innerkeys = self.external_csv_data[keys[0]].keys()
            innerkeys.sort()
            fieldnames += innerkeys

        dw = csv.DictWriter(
            open(filename,
                 "w"),
            delimiter=',',
            fieldnames=fieldnames)
        dw.writeheader()
        for xl in self.crosslinks:
            (r1, c1, r2, c2, mdist, stdv, confidence,
             unique_identifier, descriptor) = xl
            if descriptor == 'original':
                outdict = {}
                outdict["Unique ID"] = unique_identifier
                outdict["Protein1"] = c1
                outdict["Protein2"] = c2
                outdict["Residue1"] = r1
                outdict["Residue2"] = r2
                outdict["Median Distance"] = mdist
                outdict["Standard Deviation"] = stdv
                outdict["Confidence"] = confidence
                outdict["Frequency"] = self.cross_link_frequency[
                    (r1, c1, r2, c2)]
                if c1 == c2:
                    arrangement = "Intra"
                else:
                    arrangement = "Inter"
                outdict["Arrangement"] = arrangement
                if not self.external_csv_data is None:
                    outdict.update(self.external_csv_data[unique_identifier])

                dw.writerow(outdict)

    def plot(self, prot_listx=None, prot_listy=None, no_dist_info=False,
             no_confidence_info=False, filter=None, layout="whole", crosslinkedonly=False,
             filename=None, confidence_classes=None, alphablend=0.1, scale_symbol_size=1.0,
             gap_between_components=0):
        # layout can be:
        #                "lowerdiagonal"  print only the lower diagonal plot
        #                "upperdiagonal"  print only the upper diagonal plot
        #                "whole"  print all
        # crosslinkedonly: plot only components that have crosslinks
        # no_dist_info: if True will plot only the cross-links as grey spots
        # filter = tuple the tuple contains a keyword to be search in the database
        #                a relationship ">","==","<"
        #                and a value
        #                example ("ID_Score",">",40)
        # scale_symbol_size rescale the symbol for the crosslink

        import matplotlib.pyplot as plt
        import matplotlib.cm as cm
        import numpy as np

        fig = plt.figure(figsize=(10, 10))
        ax = fig.add_subplot(111)

        ax.set_xticks([])
        ax.set_yticks([])

        # set the list of proteins on the x axis
        if prot_listx is None:
            if crosslinkedonly:
                prot_listx = list(self.crosslinkedprots)
            else:
                prot_listx = self.prot_length_dict.keys()
            prot_listx.sort()

        nresx = gap_between_components + \
            sum([self.prot_length_dict[name]
                + gap_between_components for name in prot_listx])

        # set the list of proteins on the y axis

        if prot_listy is None:
            if crosslinkedonly:
                prot_listy = list(self.crosslinkedprots)
            else:
                prot_listy = self.prot_length_dict.keys()
            prot_listy.sort()

        nresy = gap_between_components + \
            sum([self.prot_length_dict[name]
                + gap_between_components for name in prot_listy])

        # this is the residue offset for each protein
        resoffsetx = {}
        resendx = {}
        res = gap_between_components
        for prot in prot_listx:
            resoffsetx[prot] = res
            res += self.prot_length_dict[prot]
            resendx[prot] = res
            res += gap_between_components

        resoffsety = {}
        resendy = {}
        res = gap_between_components
        for prot in prot_listy:
            resoffsety[prot] = res
            res += self.prot_length_dict[prot]
            resendy[prot] = res
            res += gap_between_components

        resoffsetdiagonal = {}
        res = gap_between_components
        for prot in IMP.pmi.tools.OrderedSet(prot_listx + prot_listy):
            resoffsetdiagonal[prot] = res
            res += self.prot_length_dict[prot]
            res += gap_between_components

        # plot protein boundaries

        xticks = []
        xlabels = []
        for n, prot in enumerate(prot_listx):
            res = resoffsetx[prot]
            end = resendx[prot]
            for proty in prot_listy:
                resy = resoffsety[proty]
                endy = resendy[proty]
                ax.plot([res, res], [resy, endy], 'k-', lw=0.4)
                ax.plot([end, end], [resy, endy], 'k-', lw=0.4)
            xticks.append((float(res) + float(end)) / 2)
            xlabels.append(prot)

        yticks = []
        ylabels = []
        for n, prot in enumerate(prot_listy):
            res = resoffsety[prot]
            end = resendy[prot]
            for protx in prot_listx:
                resx = resoffsetx[protx]
                endx = resendx[protx]
                ax.plot([resx, endx], [res, res], 'k-', lw=0.4)
                ax.plot([resx, endx], [end, end], 'k-', lw=0.4)
            yticks.append((float(res) + float(end)) / 2)
            ylabels.append(prot)

        # plot the contact map
        print prot_listx, prot_listy

        if not self.contactmap is None:
            from numpy import zeros
            import matplotlib.cm as cm
            tmp_array = zeros((nresx, nresy))
            for px in prot_listx:
                for py in prot_listy:
                    resx = resoffsety[px]
                    lengx = resendx[px] - 1
                    resy = resoffsety[py]
                    lengy = resendy[py] - 1
                    indexes_x = self.index_dictionary[px]
                    minx = min(indexes_x)
                    maxx = max(indexes_x)
                    indexes_y = self.index_dictionary[py]
                    miny = min(indexes_y)
                    maxy = max(indexes_y)

                    tmp_array[
                        resx:lengx,
                        resy:lengy] = self.contactmap[
                        minx:maxx,
                        miny:maxy]

                    print px, py, minx, maxx, miny, maxy
            ax.imshow(tmp_array,
                      cmap=cm.binary,
                      origin='lower',
                      interpolation='nearest')

        ax.set_xticks(xticks)
        ax.set_xticklabels(xlabels, rotation=90)
        ax.set_yticks(yticks)
        ax.set_yticklabels(ylabels)

        # set the crosslinks

        already_added_xls = []

        for xl in self.crosslinks:

            (r1, c1, r2, c2, mdist, stdv, confidence,
             unique_identifier, descriptor) = xl

            if confidence_classes is not None:
                if confidence not in confidence_classes:
                    continue

            try:
                pos1 = r1 + resoffsetx[c1]
            except:
                continue
            try:
                pos2 = r2 + resoffsety[c2]
            except:
                continue

            if not filter is None:
                xldb = self.external_csv_data[unique_identifier]
                xldb.update({"Distance": mdist})
                xldb.update({"Distance_stdv": stdv})

                if filter[1] == ">":
                    if float(xldb[filter[0]]) <= float(filter[2]):
                        continue

                if filter[1] == "<":
                    if float(xldb[filter[0]]) >= float(filter[2]):
                        continue

                if filter[1] == "==":
                    if float(xldb[filter[0]]) != float(filter[2]):
                        continue

            # all that below is used for plotting the diagonal
            # when you have a rectangolar plots

            pos_for_diagonal1 = r1 + resoffsetdiagonal[c1]
            pos_for_diagonal2 = r2 + resoffsetdiagonal[c2]

            if layout == 'lowerdiagonal':
                if pos_for_diagonal1 <= pos_for_diagonal2:
                    continue
            if layout == 'upperdiagonal':
                if pos_for_diagonal1 >= pos_for_diagonal2:
                    continue

            already_added_xls.append((r1, c1, r2, c2))

            if not no_confidence_info:
                if confidence == '0.01':
                    markersize = 14 * scale_symbol_size
                elif confidence == '0.05':
                    markersize = 9 * scale_symbol_size
                elif confidence == '0.1':
                    markersize = 6 * scale_symbol_size
                else:
                    markersize = 15 * scale_symbol_size
            else:
                markersize = 5 * scale_symbol_size

            if not no_dist_info:
                color = self.colormap(mdist)
            else:
                color = "gray"

            ax.plot(
                [pos1],
                [pos2],
                'o',
                c=color,
                alpha=alphablend,
                markersize=markersize)

        fig.set_size_inches(0.002 * nresx, 0.002 * nresy)

        [i.set_linewidth(2.0) for i in ax.spines.itervalues()]

        if filename:
            plt.savefig(filename + ".pdf", dpi=300, transparent="False")

        plt.show()

    def get_frequency_statistics(self, prot_list,
                                 prot_list2=None):

        violated_histogram = {}
        satisfied_histogram = {}
        unique_cross_links = []

        for xl in self.unique_cross_link_list:
            (r1, c1, r2, c2, sample, mdist) = xl

            # here we filter by the protein
            if prot_list2 is None:
                if not c1 in prot_list:
                    continue
                if not c2 in prot_list:
                    continue
            else:
                if c1 in prot_list and c2 in prot_list2:
                    pass
                elif c1 in prot_list2 and c2 in prot_list:
                    pass
                else:
                    continue

            frequency = self.cross_link_frequency[(r1, c1, r2, c2)]

            if (r1, c1, r2, c2) not in unique_cross_links:
                if mdist > 35.0:
                    if frequency not in violated_histogram:
                        violated_histogram[frequency] = 1
                    else:
                        violated_histogram[frequency] += 1
                else:
                    if frequency not in satisfied_histogram:
                        satisfied_histogram[frequency] = 1
                    else:
                        satisfied_histogram[frequency] += 1
                unique_cross_links.append((r1, c1, r2, c2))
                unique_cross_links.append((r2, c2, r1, c1))

        print "# satisfied"

        for i in satisfied_histogram:
            # if i in violated_histogram:
            #   print i, satisfied_histogram[i]+violated_histogram[i]
            # else:
            print i, satisfied_histogram[i]

        print "# violated"

        for i in violated_histogram:
            print i, violated_histogram[i]

# ------------
    def print_cross_link_binary_symbols(self, prot_list,
                                        prot_list2=None):
        tmp_matrix = []
        confidence_list = []
        for xl in self.crosslinks:
            (r1, c1, r2, c2, mdist, stdv, confidence,
             unique_identifier, descriptor) = xl

            if prot_list2 is None:
                if not c1 in prot_list:
                    continue
                if not c2 in prot_list:
                    continue
            else:
                if c1 in prot_list and c2 in prot_list2:
                    pass
                elif c1 in prot_list2 and c2 in prot_list:
                    pass
                else:
                    continue

            if descriptor != "original":
                continue

            confidence_list.append(confidence)

            dists = self.cross_link_distances_unique[(r1, c1, r2, c2)]
            tmp_dist_binary = []
            for d in dists:
                if d < 35:
                    tmp_dist_binary.append(1)
                else:
                    tmp_dist_binary.append(0)
            tmp_matrix.append(tmp_dist_binary)

        matrix = zip(*tmp_matrix)

        satisfied_high_sum = 0
        satisfied_mid_sum = 0
        satisfied_low_sum = 0
        total_satisfied_sum = 0
        for k, m in enumerate(matrix):
            satisfied_high = 0
            total_high = 0
            satisfied_mid = 0
            total_mid = 0
            satisfied_low = 0
            total_low = 0
            total_satisfied = 0
            total = 0
            for n, b in enumerate(m):
                if confidence_list[n] == "0.01":
                    total_high += 1
                    if b == 1:
                        satisfied_high += 1
                        satisfied_high_sum += 1
                elif confidence_list[n] == "0.05":
                    total_mid += 1
                    if b == 1:
                        satisfied_mid += 1
                        satisfied_mid_sum += 1
                elif confidence_list[n] == "0.1":
                    total_low += 1
                    if b == 1:
                        satisfied_low += 1
                        satisfied_low_sum += 1
                if b == 1:
                    total_satisfied += 1
                    total_satisfied_sum += 1
                total += 1
            print k, satisfied_high, total_high
            print k, satisfied_mid, total_mid
            print k, satisfied_low, total_low
            print k, total_satisfied, total
        print float(satisfied_high_sum) / len(matrix)
        print float(satisfied_mid_sum) / len(matrix)
        print float(satisfied_low_sum) / len(matrix)
# ------------

    def get_unique_crosslinks_statistics(self, prot_list,
                                         prot_list2=None):

        print prot_list
        print prot_list2
        satisfied_high = 0
        total_high = 0
        satisfied_mid = 0
        total_mid = 0
        satisfied_low = 0
        total_low = 0
        total = 0
        tmp_matrix = []
        satisfied_string = []
        for xl in self.crosslinks:
            (r1, c1, r2, c2, mdist, stdv, confidence,
             unique_identifier, descriptor) = xl

            if prot_list2 is None:
                if not c1 in prot_list:
                    continue
                if not c2 in prot_list:
                    continue
            else:
                if c1 in prot_list and c2 in prot_list2:
                    pass
                elif c1 in prot_list2 and c2 in prot_list:
                    pass
                else:
                    continue

            if descriptor != "original":
                continue

            total += 1
            if confidence == "0.01":
                total_high += 1
                if mdist <= 35:
                    satisfied_high += 1
            if confidence == "0.05":
                total_mid += 1
                if mdist <= 35:
                    satisfied_mid += 1
            if confidence == "0.1":
                total_low += 1
                if mdist <= 35:
                    satisfied_low += 1
            if mdist <= 35:
                satisfied_string.append(1)
            else:
                satisfied_string.append(0)

            dists = self.cross_link_distances_unique[(r1, c1, r2, c2)]
            tmp_dist_binary = []
            for d in dists:
                if d < 35:
                    tmp_dist_binary.append(1)
                else:
                    tmp_dist_binary.append(0)
            tmp_matrix.append(tmp_dist_binary)

        print "unique satisfied_high/total_high", satisfied_high, "/", total_high
        print "unique satisfied_mid/total_mid", satisfied_mid, "/", total_mid
        print "unique satisfied_low/total_low", satisfied_low, "/", total_low
        print "total", total

        matrix = zip(*tmp_matrix)
        satisfied_models = 0
        satstr = ""
        for b in satisfied_string:
            if b == 0:
                satstr += "-"
            if b == 1:
                satstr += "*"

        for m in matrix:
            all_satisfied = True
            string = ""
            for n, b in enumerate(m):
                if b == 0:
                    string += "0"
                if b == 1:
                    string += "1"
                if b == 1 and satisfied_string[n] == 1:
                    pass
                elif b == 1 and satisfied_string[n] == 0:
                    pass
                elif b == 0 and satisfied_string[n] == 0:
                    pass
                elif b == 0 and satisfied_string[n] == 1:
                    all_satisfied = False
            if all_satisfied:
                satisfied_models += 1
            print string
            print satstr, all_satisfied
        print "models that satisfies the median satisfied crosslinks/total models", satisfied_models, len(matrix)

    def plot_matrix_cross_link_distances_unique(self, figurename, prot_list,
                                                prot_list2=None):

        from numpy import zeros
        from operator import itemgetter
        import pylab as pl

        tmp_matrix = []
        for kw in self.cross_link_distances_unique:
            (r1, c1, r2, c2) = kw
            dists = self.cross_link_distances_unique[kw]

            if prot_list2 is None:
                if not c1 in prot_list:
                    continue
                if not c2 in prot_list:
                    continue
            else:
                if c1 in prot_list and c2 in prot_list2:
                    pass
                elif c1 in prot_list2 and c2 in prot_list:
                    pass
                else:
                    continue
            # append the sum of dists to order by that in the matrix plot
            dists.append(sum(dists))
            tmp_matrix.append(dists)

        tmp_matrix.sort(key=itemgetter(len(tmp_matrix[0]) - 1))

        # print len(tmp_matrix),  len(tmp_matrix[0])-1
        matrix = zeros((len(tmp_matrix), len(tmp_matrix[0]) - 1))

        for i in range(len(tmp_matrix)):
            for k in range(len(tmp_matrix[i]) - 1):
                matrix[i][k] = tmp_matrix[i][k]

        print matrix

        fig = pl.figure()
        ax = fig.add_subplot(211)

        cax = ax.imshow(matrix, interpolation='nearest')
        # ax.set_yticks(range(len(self.model_list_names)))
        #ax.set_yticklabels( [self.model_list_names[i] for i in leaves_order] )
        fig.colorbar(cax)
        pl.savefig(figurename, dpi=300)
        pl.show()

    def plot_bars(
        self,
        filename,
        prots1,
        prots2,
        nxl_per_row=20,
        arrangement="inter",
            confidence_input="None"):
        import IMP.pmi.output

        data = []
        for xl in self.cross_link_distances:
            (r1, c1, r2, c2, mdist, confidence) = xl
            if c1 in prots1 and c2 in prots2:
                if arrangement == "inter" and c1 == c2:
                    continue
                if arrangement == "intra" and c1 != c2:
                    continue
                if confidence_input == confidence:
                    label = str(c1) + ":" + str(r1) + \
                        "-" + str(c2) + ":" + str(r2)
                    values = self.cross_link_distances[xl]
                    frequency = self.cross_link_frequency[(r1, c1, r2, c2)]
                    data.append((label, values, mdist, frequency))

        sort_by_dist = sorted(data, key=lambda tup: tup[2])
        sort_by_dist = zip(*sort_by_dist)
        values = sort_by_dist[1]
        positions = range(len(values))
        labels = sort_by_dist[0]
        frequencies = map(float, sort_by_dist[3])
        frequencies = [f * 10.0 for f in frequencies]

        nchunks = int(float(len(values)) / nxl_per_row)
        values_chunks = IMP.pmi.tools.chunk_list_into_segments(values, nchunks)
        positions_chunks = IMP.pmi.tools.chunk_list_into_segments(
            positions,
            nchunks)
        frequencies_chunks = IMP.pmi.tools.chunk_list_into_segments(
            frequencies,
            nchunks)
        labels_chunks = IMP.pmi.tools.chunk_list_into_segments(labels, nchunks)

        for n, v in enumerate(values_chunks):
            p = positions_chunks[n]
            f = frequencies_chunks[n]
            l = labels_chunks[n]
            IMP.pmi.output.plot_fields_box_plots(
                filename + "." + str(n), v, p, f,
                valuename="Distance (Ang)", positionname="Unique " + arrangement + " Crosslinks", xlabels=l)

    def crosslink_distance_histogram(self, filename,
                                     prot_list=None,
                                     prot_list2=None,
                                     confidence_classes=None,
                                     bins=40,
                                     color='#66CCCC',
                                     yplotrange=[0, 1],
                                     format="png",
                                     normalized=False):
        if prot_list is None:
            prot_list = self.prot_length_dict.keys()

        distances = []
        for xl in self.crosslinks:
            (r1, c1, r2, c2, mdist, stdv, confidence,
             unique_identifier, descriptor) = xl

            if not confidence_classes is None:
                if confidence not in confidence_classes:
                    continue

            if prot_list2 is None:
                if not c1 in prot_list:
                    continue
                if not c2 in prot_list:
                    continue
            else:
                if c1 in prot_list and c2 in prot_list2:
                    pass
                elif c1 in prot_list2 and c2 in prot_list:
                    pass
                else:
                    continue

            distances.append(mdist)

        IMP.pmi.output.plot_field_histogram(
            filename, distances, valuename="C-alpha C-alpha distance [Ang]",
            bins=bins, color=color,
            format=format,
            reference_xline=35.0,
            yplotrange=yplotrange, normalized=normalized)

    def scatter_plot_xl_features(self, filename,
                                 feature1=None,
                                 feature2=None,
                                 prot_list=None,
                                 prot_list2=None,
                                 yplotrange=None,
                                 reference_ylines=None,
                                 distance_color=True,
                                 format="png"):
        import matplotlib.pyplot as plt
        import matplotlib.cm as cm
        import numpy as np

        fig = plt.figure(figsize=(10, 10))
        ax = fig.add_subplot(111)

        for xl in self.crosslinks:
            (r1, c1, r2, c2, mdist, stdv, confidence,
             unique_identifier, arrangement) = xl

            if prot_list2 is None:
                if not c1 in prot_list:
                    continue
                if not c2 in prot_list:
                    continue
            else:
                if c1 in prot_list and c2 in prot_list2:
                    pass
                elif c1 in prot_list2 and c2 in prot_list:
                    pass
                else:
                    continue

            xldb = self.external_csv_data[unique_identifier]
            xldb.update({"Distance": mdist})
            xldb.update({"Distance_stdv": stdv})

            xvalue = float(xldb[feature1])
            yvalue = float(xldb[feature2])

            if distance_color:
                color = self.colormap(mdist)
            else:
                color = "gray"

            ax.plot([xvalue], [yvalue], 'o', c=color, alpha=0.1, markersize=7)

        if not yplotrange is None:
            ax.set_ylim(yplotrange)
        if not reference_ylines is None:
            for rl in reference_ylines:
                ax.axhline(rl, color='red', linestyle='dashed', linewidth=1)

        if filename:
            plt.savefig(filename + "." + format, dpi=150, transparent="False")

        plt.show()

#
# these are post production function analysis
#


def get_hier_from_rmf(model, frame_number, rmf_file):
    import IMP.rmf
    import RMF
    print "getting coordinates for frame %i rmf file %s" % (frame_number, rmf_file)

    # load the frame
    rh = RMF.open_rmf_file_read_only(rmf_file)

    try:
        prots = IMP.rmf.create_hierarchies(rh, model)
    except:
        print "Unable to open rmf file %s" % (rmf_file)
        prot = None
        return prot
    #IMP.rmf.link_hierarchies(rh, prots)
    prot = prots[0]
    try:
        IMP.rmf.load_frame(rh, frame_number)
    except:
        print "Unable to open frame %i of file %s" % (frame_number, rmf_file)
        prot = None
    model.update()
    del rh
    return prot


def get_particles_at_resolution_one(prot):
    '''
    this fucntion get the particles by resolution, without a Representation class initialized
    it is mainly used when the hierarchy is read from an rmf file
    it returns a dictionary of component names and their particles
    '''
    particle_dict = {}
    allparticles = []
    for c in prot.get_children():
        name = c.get_name()
        particle_dict[name] = IMP.atom.get_leaves(c)
        for s in c.get_children():
            if "_Res:1" in s.get_name() and "_Res:10" not in s.get_name():
                allparticles += IMP.atom.get_leaves(s)
            if "Beads" in s.get_name():
                allparticles += IMP.atom.get_leaves(s)

    particle_align = []
    for name in particle_dict:

        particle_dict[name] = IMP.pmi.tools.sort_by_residues(
            list(set(particle_dict[name]) & set(allparticles)))

    return particle_dict


def select_by_tuple(first_res_last_res_name_tuple):
    first_res = first_res_last_res_hier_tuple[0]
    last_res = first_res_last_res_hier_tuple[1]
    name = first_res_last_res_hier_tuple[2]
