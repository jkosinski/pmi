import IMP
import IMP.atom
import IMP.pmi
from collections import defaultdict
import IMP.pmi.structure_tools
from Bio import SeqIO

"""
A new representation module. It helps to construct the hierarchy
and deal with multi-state, multi-scale, multi-copies

Usage Example:

see representation_new_test.py

For each of the classes System, State, and Molecule, you store the root node and
  references to child classes (System>State>Molecule).
When you call build() on any of these classes, build() is also called for each of the child classes,
and the root IMP hierarchy is returned.
"""

#------------------------


class _SystemBase(object):
    """This is the base class for System, _State and _Molecule
    classes. It contains shared functions in common to these classes
    """

    def __init__(self,mdl=None):
        if mdl is None:
            self.mdl=IMP.Model()
        else:
            self.mdl=mdl

    def _create_hierarchy(self):
        """create a new hierarchy"""
        tmp_part=IMP.kernel.Particle(self.mdl)
        return IMP.atom.Hierarchy.setup_particle(tmp_part)

    def _create_child(self,parent_hierarchy):
        """create a new hierarchy, set it as child of the input
        one, and return it"""
        child_hierarchy=self._create_hierarchy()
        parent_hierarchy.add_child(child_hierarchy)
        return child_hierarchy

    def build(self):
        """Build the coordinates of the system.
        Loop through stored(?) hierarchies and set up coordinates!"""
        pass

#------------------------

class System(_SystemBase):
    """This class initializes the root node of the global IMP.atom.Hierarchy."""
    def __init__(self,mdl=None):
        _SystemBase.__init__(self,mdl)
        self._number_of_states = 0
        self.states = []
        self.built=False

        # the root hierarchy node
        self.system=self._create_hierarchy()
        self.system.set_name("System")

    def create_state(self):
        """returns a new IMP.pmi.representation_new._State(), increment the state index"""
        self._number_of_states+=1
        state = _State(self.system,self._number_of_states-1)
        self.states.append(state)
        return state

    def get_number_of_states(self):
        """returns the total number of states generated"""
        return self._number_of_states

    def build(self):
        """call build on all states"""
        if not self.built:
            for state in self.states:
                state.build()
            self.built=True
        return self.system


#------------------------

class _State(_SystemBase):
    """This private class is constructed from within the System class.
    It wraps an IMP.atom.State
    """
    def __init__(self,system_hierarchy,state_index):
        """Define a new state
        @param system_hierarchy     the parent root hierarchy
        @param state_index          the index of the new state
        """
        self.mdl = system_hierarchy.get_model()
        self.system = system_hierarchy
        self.state = self._create_child(system_hierarchy)
        self.state.set_name("State_"+str(state_index))
        self.molecules = []
        IMP.atom.State.setup_particle(self.state,state_index)
        self.built=False

    def create_molecule(self,name,sequence=None,molecule_to_copy=None):
        """Create a new Molecule within this State
        @param name                the name of the molecule (string) it must not
                                   contain underscores characters "_" and must not
                                   be already used
        @param sequence            sequence (string)
        """
        # check the presence of underscores
        if "_" in name:
           raise WrongMoleculeName('A molecule name should not contain underscores characters')

        # check whether the molecule name is already assigned
        if name in [mol.name for mol in self.molecules]:
           raise WrongMoleculeName('Cannot use a molecule name already used')

        mol = _Molecule(self.state,name,sequence)
        self.molecules.append(mol)
        return mol

    def build(self):
        """call build on all molecules (automatically makes copies)"""
        if not self.built:
            for mol in self.molecules:
                mol.build()
            self.built=True
        return self.state

#------------------------

class _Molecule(_SystemBase):
    """This private class is constructed from within the State class.
    It wraps an IMP.atom.Molecule and IMP.atom.Copy
    Structure is read using this class
    Resolutions and copies can be registered, but are only created when build() is called
    """

    def __init__(self,state_hierarchy,name,sequence):
        """Create copy 0 of this molecule.
        Arguments:
        @param state_hierarchy     the parent State-decorated hierarchy (IMP.atom.Hierarchy)
        @param name                the name of the molecule (string)
        @param sequence            sequence (string)
        """
        # internal data storage
        self.mdl=state_hierarchy.get_model()
        self.state=state_hierarchy
        self.name=name
        self.sequence=sequence
        self.number_of_copies=1
        self.built=False

        # create root node and set it as child to passed parent hierarchy
        self.molecule=self._create_child(self.state)
        self.molecule.set_name(self.name+"_0")
        IMP.atom.Copy.setup_particle(self.molecule,0)

        # create Residues from the sequence
        self.residues=[]
        for ns,s in enumerate(sequence):
            r=_Residue(self,s,ns+1)
            self.residues.append(r)

    def __repr__(self):
        return self.state.get_name()+'_'+self.name

    def __getitem__(self,val):
        if isinstance(val,int):
            return self.residues[val]
        elif isinstance(val,str):
            return self.residues[int(val)-1]
        elif isinstance(val,slice):
            return set(self.residues[val])
        else:
            print "ERROR: range ends must be int or str. Stride must be int."


    def residue_range(self,a,b,stride=1):
        """get residue range. Use integers to get 0-indexing, or strings to get PDB-indexing"""
        if isinstance(a,int) and isinstance(b,int) and isinstance(stride,int):
            return set(self.residues[a:b:stride])
        elif isinstance(a,str) and isinstance(b,str) and isinstance(stride,int):
            return set(self.residues[int(a)-1:int(b)-1:stride])
        else:
            print "ERROR: range ends must be int or str. Stride must be int."


    def add_copy(self):
        """Register a new copy of the Molecule.
        Copies are only constructed when build() is called.
        """
        self.number_of_copies+=1

    def add_structure(self,pdb_fn,chain,res_range=None,offset=0):
        """Read a structure and store the coordinates.
        Returns the atomic residues (as a set)
        @param pdb_fn    The file to read
        @param chain     Chain ID to read
        @param res_range Add only a specific set of residues
        @param offset    Apply an offset to the residue indexes of the PDB file
        \note After offset, we expect the PDB residue numbering to match the FASTA file
        """
        # get IMP.atom.Residues from the pdb file
        rhs=IMP.pmi.structure_tools.get_structure(self.mdl,pdb_fn,chain,res_range,offset)
        if len(rhs)>len(self.residues):
            print 'ERROR: You are loading',len(rhs), \
                'pdb residues for a sequence of length',len(self.residues),'(too many)'

        # load those into the existing pmi Residue objects, and return contiguous regions
        atomic_res=set() # collect integer indexes of atomic residues!
        for nrh,rh in enumerate(rhs):
            idx=rh.get_index()
            internal_res=self.residues[idx-1]
            if internal_res.get_code()!=IMP.atom.get_one_letter_code(rh.get_residue_type()):
                print 'ERROR: PDB residue is',IMP.atom.get_one_letter_code(rh.get_residue_type()), \
                    'and sequence residue is',internal_res.get_code()
            internal_res.set_structure(rh)
            atomic_res.add(internal_res)
        return atomic_res

    def add_representation(self,res_set=None,representation_type="balls",resolutions=[]):
        """handles the IMP.atom.Representation decorators, such as multi-scale,
        density, etc."""
        allowed_types=("balls")
        if representation_type not in allowed_types:
            print "ERROR: Allowed representation types:",allowed_types
            return
        if res_set is None:
            res_set=set(self.residues)
        for res in res_set:
            res.add_representation(representation_type,resolutions)

    def build(self,merge_type="backbone",ca_centers=True,fill_in_missing_residues=True):
        """Create all parts of the IMP hierarchy
        including Atoms, Residues, and Fragments/Representations and, finally, Copies
        /note Any residues assigned a resolution must have an IMP.atom.Residue hierarchy
              containing at least a CAlpha. For missing residues, these can be constructed
              from the PDB file

        @param merge_type Principle for grouping into fragments.
                          "backbone": linear sequences along backbone are grouped
                          into fragments if they have identical sets of representations.
                          "volume": at each resolution, groups are made based on
                          spatial distance (not currently implemented)
        @param ca_centers For single-bead-per-residue only. Set the center over the CA position.
        """
        allowed_types=("backbone")
        if merge_type not in allowed_types:
            print "ERROR: Allowed merge types:",allowed_types
            return
        if not self.built:
            # fill in missing residues
            #  for every Residue with tagged representation, build an IMP.atom.Residue and CAlpha


            # group into Fragments along backbone
            if merge_type=="backbone":
                IMP.pmi.structure_tools.build_along_backbone(self.mdl,self.molecule,self.residues,
                                                             IMP.atom.BALLS,ca_centers)


            # group into Fragments by volume
            elif merge_type=="volume":
                pass

            # create requested number of copies
            for nc in range(1,self.number_of_copies):
                mhc=self._create_child(self.state)
                mhc.set_name(self.name+"_%i"%nc)
                IMP.atom.Copy.setup_particle(mhc,nc)
                # TODO: DEEP COPY all representations, fragments, residues, and atoms
                # ...

            self.built=True
        #IMP.atom.show_molecular_hierarchy(self.molecule)
        return self.molecule


#------------------------

class Sequences(object):
    """A dictionary-like wrapper for reading and storing sequence data"""
    def __init__(self,fasta_fn,name_map=None):
        """read a fasta file and extract all the requested sequences
        @param fasta_fn sequence file
        @param name_map dictionary mapping the fasta name to the stored name
        """
        self.sequences={}
        self.read_sequences(fasta_fn,name_map)
    def __len__(self):
        return len(self.sequences)
    def __contains__(self,x):
        return x in self.sequences
    def __getitem__(self,key):
        return self.sequences[key]
    def read_sequences(self,fasta_fn,name_map=None):
        # read all sequences
        handle = open(fasta_fn, "rU")
        record_dict = SeqIO.to_dict(SeqIO.parse(handle, "fasta"))
        handle.close()
        if name_map is None:
            for pn in record_dict:
                self.sequences[pn]=str(record_dict[pn].seq).replace("*", "")
        else:
            for pn in name_map:
                try:
                    self.sequences[name_map[pn]]=str(record_dict[pn].seq).replace("*", "")
                except:
                    print "tried to add sequence but: id %s not found in fasta file" % pn
                    exit()

#------------------------


class _Residue(object):
    """Stores basic residue information, even without structure available."""
    # Consider implementing __hash__ so you can select.
    def __init__(self,molecule,code,index):
        """setup a Residue
        @param molecule PMI Molecule to which this residue belongs
        @param code     one-letter residue type code
        @param index    PDB index
        """
        self.molecule = molecule
        self.hier = IMP.atom.Residue.setup_particle(IMP.Particle(molecule.mdl),
                                                    IMP.pmi.sequence_tools.get_residue_type_from_one_letter_code(code),
                                                    index)
        self.representations = defaultdict(set)
    def __str__(self):
        return self.get_code()
    def __repr__(self):
        return self.__str__()
    def __key(self):
        return (self.molecule,self.hier,
                frozenset((k,tuple(self.representations[k])) for k in self.representations))
    def __eq__(self,other):
        return type(other)==type(self) and self.__key() == other.__key()
    def __hash__(self):
        return hash(self.__key())
    def get_index(self):
        return self.hier.get_index()
    def get_code(self):
        return IMP.atom.get_one_letter_code(self.hier.get_residue_type())
    def get_residue_type(self):
        return self.hier.get_residue_type()
    def set_structure(self,res):
        if res.get_residue_type()!=self.hier.get_residue_type():
            print "ERROR: adding structure to this residue, but it's the wrong type!"
            sys.exit()
        for a in res.get_children():
            self.hier.add_child(a)
    def add_representation(self,rep_type,resolutions):
        self.representations[rep_type] |= set(resolutions)
