from __future__ import print_function

import ihm.format
import IMP.test
import IMP.pmi.topology
import IMP.pmi.mmcif
import sys

if sys.version_info[0] >= 3:
    from io import StringIO
else:
    from io import BytesIO as StringIO

class MockMsgPack(object):
    @staticmethod
    def pack(data, fh):
        fh.data = data


class MockFh(object):
    pass


class DummyPO(IMP.pmi.mmcif.ProtocolOutput):
    def flush(self):
        pass

class Tests(IMP.test.TestCase):

    def assign_entity_asym_ids(self, system):
        """Assign IDs to all Entities and AsymUnits in the system"""
        d = ihm.dumper._EntityDumper()
        d.finalize(system)
        d = ihm.dumper._StructAsymDumper()
        d.finalize(system)

    def test_component_mapper(self):
        """Test ComponentMapper with PMI2 topology"""
        m = IMP.Model()
        s = IMP.pmi.topology.System(m)
        po = DummyPO(None)
        s.add_protocol_output(po)
        state = s.create_state()
        nup84 = state.create_molecule("Nup84", "MELS", "A")
        nup84.add_representation(resolutions=[1])
        hier = s.build()
        c = IMP.pmi.mmcif._ComponentMapper(hier)
        r = IMP.atom.get_by_type(hier, IMP.atom.RESIDUE_TYPE)[1]
        self.assertEqual(c[r], 'Nup84.0')

    def test_hier_system_mapping(self):
        """Test mapping from Hierarchy back to System"""
        m = IMP.Model()
        s = IMP.pmi.topology.System(m)
        po = DummyPO(None)
        s.add_protocol_output(po)
        state = s.create_state()
        hier = s.build()

        # Check mapping from Hierarchy back to System
        self.assertEqual(IMP.pmi.tools._get_system_for_hier(hier), s)
        self.assertEqual(IMP.pmi.tools._get_system_for_hier(None), None)
        # Check mapping from Hierarchy to ProtocolOutput
        pos = list(IMP.pmi.tools._all_protocol_outputs([], hier))
        # Should be a list of (ProtocolOuput, State) tuples
        self.assertEqual(len(pos), 1)
        self.assertEqual(len(pos[0]), 2)
        self.assertEqual(pos[0][0], po)

    def test_finalize_flush_mmcif(self):
        """Test ProtocolOutput.finalize() and .flush() with mmCIF output"""
        m = IMP.Model()
        s = IMP.pmi.topology.System(m)
        fh = StringIO()
        po = IMP.pmi.mmcif.ProtocolOutput(fh)
        s.add_protocol_output(po)
        po.flush()
        self.assertEqual(fh.getvalue().split('\n')[:4],
                         ['data_model', '_entry.id model',
                          '_struct.entry_id model', '_struct.title .'])

    def test_finalize_flush_bcif(self):
        """Test ProtocolOutput.finalize() and .flush() with BinaryCIF output"""
        m = IMP.Model()
        s = IMP.pmi.topology.System(m)
        fh = MockFh()
        sys.modules['msgpack'] = MockMsgPack
        po = IMP.pmi.mmcif.ProtocolOutput(fh)
        s.add_protocol_output(po)
        po.flush(format='BCIF')
        self.assertEqual(fh.data[b'dataBlocks'][0][b'categories'][0][b'name'],
                         b'_entry')

    def test_entity(self):
        """Test EntityDump with PMI2-style init"""
        m = IMP.Model()
        s = IMP.pmi.topology.System(m)
        po = DummyPO(None)
        s.add_protocol_output(po)
        state = s.create_state()
        nup84 = state.create_molecule("Nup84", "MELS", "A")
        nup84.add_representation(resolutions=[1])
        hier = s.build()
        fh = StringIO()
        w = ihm.format.CifWriter(fh)
        d = ihm.dumper._EntityDumper()
        d.finalize(po.system)
        d.dump(po.system, w)
        out = fh.getvalue()
        self.assertEqual(out, """#
loop_
_entity.id
_entity.type
_entity.src_method
_entity.pdbx_description
_entity.formula_weight
_entity.pdbx_number_of_molecules
_entity.details
1 polymer man Nup84 532.606 1 .
#
""")

    def test_model_representation(self):
        """Test ModelRepresentationDumper with PMI2-style init"""
        m = IMP.Model()
        s = IMP.pmi.topology.System(m)
        po = DummyPO(None)
        s.add_protocol_output(po)
        state = s.create_state()
        nup84 = state.create_molecule("Nup84", "MELS", "A")
        nup84.add_structure(self.get_input_file_name('test.nup84.pdb'), 'A')
        nup84.add_representation(resolutions=[1])
        hier = s.build()
        fh = StringIO()
        w = ihm.format.CifWriter(fh)
        self.assign_entity_asym_ids(po.system)
        # Assign starting model IDs
        d = ihm.dumper._StartingModelDumper()
        d.finalize(po.system)
        d = ihm.dumper._ModelRepresentationDumper()
        d.finalize(po.system)
        d.dump(po.system, w)
        out = fh.getvalue()
        self.assertEqual(out, """#
loop_
_ihm_model_representation.ordinal_id
_ihm_model_representation.representation_id
_ihm_model_representation.segment_id
_ihm_model_representation.entity_id
_ihm_model_representation.entity_description
_ihm_model_representation.entity_asym_id
_ihm_model_representation.seq_id_begin
_ihm_model_representation.seq_id_end
_ihm_model_representation.model_object_primitive
_ihm_model_representation.starting_model_id
_ihm_model_representation.model_mode
_ihm_model_representation.model_granularity
_ihm_model_representation.model_object_count
1 1 1 1 Nup84 A 1 2 sphere 1 flexible by-residue .
2 1 2 1 Nup84 A 3 4 sphere . flexible by-feature 2
#
""")

if __name__ == '__main__':
    IMP.test.main()
