import itertools
import os
import numpy as np

from ff_energy.ffe.templates import PSF

import ff_energy as constants
from ase.io import read

from scipy.spatial import distance_matrix as DM


def sqrt_einsum_T(data):
    a, b = data[1]
    a_min_b = a - b
    return np.sqrt(np.einsum("ij,ij->j", a_min_b, a_min_b))


def _sqrt_einsum_T(a, b):
    a_min_b = a - b
    return np.sqrt(np.einsum("ij,ij->j", a_min_b, a_min_b))


def valid_atom_key_pairs(atom_keys):
    atom_key_pairs = list(itertools.combinations(atom_keys, 2))
    atom_key_pairs = [(a, b) if a < b else (b, a) for a, b in atom_key_pairs]
    atom_key_pairs.extend([(a, a) for a in atom_keys])
    atom_key_pairs.sort(key=lambda x: (x[0], x[1]))
    return atom_key_pairs


atom_keys = ["OG311", "CG331", "HGP1", "HGA3", "OT", "HT",
             "C", "H", "CL", "CLA", "POT"]

atom_keys.sort()

atom_key_pairs = valid_atom_key_pairs(atom_keys)
for i, _ in enumerate(atom_key_pairs):
    print(i, _)

atom_name_fix = {"CL": "Cl", "PO": "K", "CLA": "Cl", "POT": "K", "Pot": "K"}


def get_atom_names(atoms):
    ans = np.array([_.split()[2] for _ in atoms])
    for i, _ in enumerate(ans):
        for k in atom_name_fix.keys():
            if k in _:
                ans[i] = atom_name_fix[k]
    return ans


class Structure:
    """Class for a pdb structure"""

    def __init__(self, path, _atom_types=None, system_name=None):
        #  assign atom types
        if _atom_types is None:
            atom_types = constants.atom_types
        else:
            atom_types = _atom_types

        self.system_name = system_name
        self.path = path
        self.name = os.path.basename(path)
        self.lines = None
        self.atoms = None
        self.atomnames = None
        self.keys = None
        self.resids = None
        self.restypes = None
        self.xyzs = None
        self.chm_typ = None
        self.chm_typ_mask = None
        self.res_mask = None
        self.pairs = None
        self.distances = None
        self.distances_pairs = None
        self.distances_mask = None
        self.dcm = None
        self.dcm_charges = None
        self.dcm_charges_mask = None
        self.atom_types = atom_types

        self.read_pdb(self.path)

    def get_cluster_charge(self):
        chg = 0
        for i, _ in enumerate(self.restypes):
            if _ == "CLA":
                chg -= 1
            elif _ == "POT":
                chg += 1
        return chg

    def get_monomer_charge(self, n):
        chg = 0
        restypes = np.array(self.restypes)
        for i, _ in enumerate(restypes[self.res_mask[n]]):
            if _ == "CLA":
                chg -= 1
            elif _ == "POT":
                chg += 1
        return chg

    def get_pair_charge(self, res_a, res_b):
        restypes = np.array(self.restypes)
        res_types = restypes[self.res_mask[res_a] + self.res_mask[res_b]]
        chg = 0
        for i, _ in enumerate(res_types):
            if _ == "CLA":
                chg -= 1
            elif _ == "POT":
                chg += 1
        return chg

    def read_pdb(self, path):
        self.lines = open(path).readlines()
        self.atoms = [
            _ for _ in self.lines if _.startswith("ATOM") or _.startswith("HETATM")
        ]
        self.atomnames = get_atom_names(self.atoms)
        self.keys = [(_[17:21].strip(), _[12:17].strip()) for _ in self.atoms]
        self.resids = [int(_[22:27].strip()) for _ in self.atoms]

        # openbabel sometimes gives resids of 0
        # this is a hack to fix that
        for i, _ in enumerate(self.resids):
            if _ == 0:
                self.resids[i] = self.resids[i - 1]

        self.n_res = len(set(self.resids))
        resids_old = list(set(self.resids))
        resids_old.sort()
        resids_new = list(range(1, len(resids_old) + 1))

        # print(self.resids)
        self.resids = [resids_new[resids_old.index(_)] for _ in self.resids]
        # print(self.resids)

        self.restypes = [_[16:21].strip() for _ in self.atoms]
        self.xyzs = np.array(
            [[float(_[30:38]), float(_[39:46]), float(_[47:55])] for _ in self.atoms]
        )
        # print(self.restypes, self.atomnames)
        # print(self.atom_types)
        self.chm_typ = np.array(
            [self.atom_types[(
                a.upper(),
                b.upper()
            )] for a, b in zip(self.restypes, self.atomnames)]
        )
        self.chm_typ_mask = {
            ak.upper(): np.array([ak.upper() == _ for _ in self.chm_typ]) for ak in atom_keys
        }
        self.res_mask = {
            r: np.array([r == _ for _ in self.resids]) for r in list(set(self.resids))
        }
        #  give the water molecules a consistent name
        self.restypes = ["TIP3" if "HOH" in _ else _ for _ in self.restypes]

        for i, (resid, atmname) in enumerate(zip(self.restypes, self.atomnames)):
            if resid == "TIP3":
                # print("**", i, resid, atmname)
                if atmname == "H" and self.atomnames[i - 1] == "O":
                    self.atomnames[i] = "H1"
                    self.atomnames[i + 1] = "H2"

    def load_dcm(self, path, dcm_charges_per_res=None):
        """Load dcm file"""
        self.n_res = len(set(self.resids))
        with open(path) as f:
            lines = f.readlines()
        self.dcm = [
            [float(_) for _ in line.split()[1:]] for line in lines[2:]
        ]  # skip first two lines
        self.dcm_charges = self.dcm[len(self.atoms):]
        if dcm_charges_per_res is None:
            dcm_charges_per_res = len(self.dcm_charges) // self.n_res // 3

        #  make a dictionary which holds the
        #  mask for dcm charges
        #  listing the idxs of the charges for each residue type
        self.dcm_charges_mask = {
            r: np.array(
                [
                    [True] * dcm_charges_per_res
                    if r == _
                    else [False] * dcm_charges_per_res
                    for _ in range(1, self.n_res + 1)  # for each residue
                ]
            ).flatten()
            for r in list(set(self.resids))  # for each residue type
        }

    def get_psf(self):
        """Get psf file for structure"""
        OM = ["O"]
        CM = ["C"]
        H1M = ["H1"]
        H2M = ["H2"]
        H3M = ["H3"]
        H4M = ["H4"]
        OATOM = ["O", "OH2"]
        OATOM = [_ for _ in OATOM if _ in [x[1] for x in self.atom_types.keys()]]
        H = ["H", "H1"]
        H = [_ for _ in H if _ in [x[1] for x in self.atom_types.keys()]]
        H1 = ["H", "H1"]
        if H[0] == "H":
            H1 = ["H1"]
        if H[0] == "H1":
            H1 = ["H2"]

        METHANOL = "MEO"
        WATER = "LIG"

        if "TIP3" in [x[0] for x in self.atom_types.keys()]:
            WATER = "TIP3"
            METHANOL = "LIG"
        if "HOH" in [x[0] for x in self.atom_types.keys()]:
            WATER = "TIP3"
            METHANOL = "LIG"

        return PSF.render(
            OM=OM[0],
            CM=CM[0],
            H1M=H1M[0],
            H2M=H2M[0],
            H3M=H3M[0],
            H4M=H4M[0],
            O="OH2",  # TODO: possible breaking change
            H="H1",
            H1="H2",
            WATER=WATER,
            METHANOL=METHANOL,
        )

    def set_2body(self):
        """Set 2-body distances"""
        #  all interacting pairs
        # print(self.resids)
        # print(atom_key_pairs)
        #  all combination of pairs
        self.pairs = list(itertools.combinations(
            range(1, max(self.resids) + 1), 2)
        )
        self.distances = [[] for _ in range(len(atom_key_pairs))]
        self.distances_pairs = [{} for _ in range(len(atom_key_pairs))]

        for res_a, res_b in self.pairs:
            for i, akp in enumerate(atom_key_pairs):
                a, b = akp
                cond1 = a in self.chm_typ_mask.keys()
                cond2 = b in self.chm_typ_mask.keys()
                if cond1 and cond2:
                    #  exclude any missing keys
                    if not np.all(self.chm_typ_mask[a]) \
                            and not np.all(self.chm_typ_mask[b]):

                        # print(a, b)

                        #  get the mask for the atom types, residues
                        mask_a = self.chm_typ_mask[a]
                        res_mask_a = self.res_mask[res_a]
                        mask_b = self.chm_typ_mask[b]
                        res_mask_b = self.res_mask[res_b]
                        xyza = self.xyzs[mask_a * res_mask_a]
                        xyzb = self.xyzs[mask_b * res_mask_b]
                        # xyza = np.repeat(xyza, xyza.shape[0], axis=0)
                        # xyzb = np.repeat(xyzb_, xyzb_.shape[0], axis=0)

                        #  case for same atom types
                        if xyza.shape[0] > 0 and xyzb.shape[0] > 0:
                            # print(".")
                            # _d = np.linalg.norm(xyza - xyzb, axis=1)
                            _d = DM(xyza, xyzb)#.flatten()
                            self.distances_pairs[i][(res_a, res_b)] = []

                            self.distances[i].append(_d)
                            self.distances_pairs[i][(res_a, res_b)].append(_d)

                        # case for different atom types
                        if a != b:
                            # b, a = akp
                            res_b, res_a = res_a, res_b
                            mask_a = self.chm_typ_mask[a]
                            res_mask_a = self.res_mask[res_a]
                            mask_b = self.chm_typ_mask[b]
                            res_mask_b = self.res_mask[res_b]
                            xyza = self.xyzs[mask_a * res_mask_a]
                            xyzb = self.xyzs[mask_b * res_mask_b]
                            # xyza = np.repeat(xyza_, xyzb_.shape[0], axis=0)
                            # xyzb = np.repeat(xyzb_, xyza_.shape[0], axis=0)

                            if xyza.shape[0] > 0 and xyzb.shape[0] > 0:
                                # print(".")
                                # _d = _sqrt_einsum_T(xyza.T, xyzb.T)
                                # _d = np.linalg.norm((xyza - xyzb), axis=1)

                                _d = DM(xyza, xyzb)#.flatten()
                                # print("DM", _d)
                                # print(a, b, res_a, res_b, _d)
                                self.distances[i].append(_d)
                                if (res_b, res_a) not in self.distances_pairs[i].keys():
                                    self.distances_pairs[i][(res_b, res_a)] = []
                                self.distances_pairs[i][(res_b, res_a)].append(_d)

    def get_monomers(self):
        """returns list of monomers"""
        out = list(set(self.resids))
        out.sort()
        return out

    def get_pairs(self):
        return self.pairs

    def get_monomer_xyz(self, res):
        """returns xyz coordinates of all atoms in residue res"""
        atom_names = self.atomnames[self.res_mask[res]]
        xyz = self.xyzs[self.res_mask[res]]
        return self.get_xyz_string(xyz, atom_names)

    def get_pair_xyz(self, res_a, res_b):
        """returns xyz coordinates of all atoms in residue res"""
        atom_names = self.atomnames[self.res_mask[res_a] + self.res_mask[res_b]]
        xyz = self.xyzs[self.res_mask[res_a] + self.res_mask[res_b]]
        return self.get_xyz_string(xyz, atom_names)

    def get_cluster_xyz(self):
        """returns xyz coordinates of all atoms in cluster"""
        atom_names = self.atomnames
        xyz = self.xyzs
        return self.get_xyz_string(xyz, atom_names)

    def get_xyz_string(self, xyz, atomnames):
        """returns a string in the format atomname x y z for all atoms in xyz"""
        xyz_string = ""
        for i, atom in enumerate(atomnames):
            #  TODO: general way of getting around elements with two letters
            a = atom[:2] if (atom.startswith("CL")) else atom[:1]
            #  TODO: avoid this hack
            if a == "P":
                a = "K"
            xyz_string += "{} {:8.3f} {:8.3f} {:8.3f}\n".format(
                a, xyz[i, 0], xyz[i, 1], xyz[i, 2]
            )
        return xyz_string

    def get_pdb(self):
        header = """HEADER
TITLE
REMARK
"""
        pdb_format = (
            "{:6s}{:5d} {:<4s}{:1s}{:4s}{:1s}{:4d}{:1s}   "
            "{:8.3f}{:8.3f}{:8.3f}{:6.2f}{:6.2f}"
            "          {:>2s}{:2s}\n"
        )
        _str = header
        last_resid = self.resids[0]
        res_id_count = 1

        res_ids_ = []

        for i, line in enumerate(self.atoms):
            AN = self.atomnames[i]
            RESNAME = self.restypes[i]

            # print(i, RESNAME)

            if AN == "Cl":
                # print(i, line)
                if self.atomnames[i - 1] == "CL1":
                    AN = "CL2"
                    self.atomnames[i] = "CL2"
                else:
                    AN = "CL1"
                    self.atomnames[i] = "CL1"

                # print(self.atomnames[i], AN)

            if RESNAME == "CLA":
                AN = "CLA"
                self.atomnames[i] = "CLA"
            if RESNAME == "CLA":
                AN = "CLA"
                self.atomnames[i] = "CLA"
            if RESNAME == "DCM" and AN.__contains__("H"):
                if self.atomnames[i - 1].__contains__("H"):
                    # print("H2")
                    AN = "H2"
                    self.atomnames[i] = "H" #"H2"
                else:
                    AN = "H1"
                    self.atomnames[i] = "H" #"H1"
                    # print("H1")

            if RESNAME == "TIP3":
                if self.atomnames[i].startswith("H"):
                    self.atomnames[i] = "HT"
                    if i == 1 or i == 4:
                        AN = "H1"
                    else:
                        AN = "H2"
                    #  TODO: check if this is correct for ions, etc.
                    if (i + 1) % 3:
                        AN = "H1"
                    else:
                        AN = "H2"

                if self.atomnames[i].startswith("O"):
                    self.atomnames[i] = "OT"
                    AN = "OH2"

            if self.resids[i] != last_resid:
                res_id_count += 1
                last_resid = self.resids[i]

            RESTYPE = self.restypes[i].upper()
            if AN == "K":
                AN = "POT"
                self.atomnames[i] = "POT"



            _1 = "ATOM"
            _2 = i + 1
            _3 = AN.upper()
            _4 = ""
            _5 = RESTYPE
            _6 = ""
            _7 = res_id_count  # self.resids[i]
            _8 = ""
            _9 = self.xyzs[i, 0]
            _10 = self.xyzs[i, 1]
            _11 = self.xyzs[i, 2]
            _12 = 0.0
            _13 = 0.0
            _14 = self.atomnames[i]
            _15 = " "
            _ = pdb_format.format(
                _1, _2, _3, _4, _5, _6, _7, _8, _9, _10, _11, _12, _13, _14, _15
            )
            _str += _
        _str += "END"
        return _str

    def save_pdb(self, path):
        with open(path, "w") as f:
            f.write(self.get_pdb())

    def save_xyz(self, path):
        with open(path, "w") as f:
            s = self.get_cluster_xyz()
            f.write(f"{len(self.atoms)}\nFFE output\n")
            f.write(s)

    def save_monomer_xyz(self, res, path):
        with open(path, "w") as f:
            f.write(self.get_monomer_xyz(res))

    def save_pair_xyz(self, res_a, res_b, path):
        with open(path, "w") as f:
            f.write(self.get_pair_xyz(res_a, res_b))

    def get_ase(self):
        """returns ase atoms object
        workaround by saving to file..."""
        name = str(self.path.absolute()) + ".tmp.xyz"
        # make the dir if not exists
        os.makedirs(os.path.dirname(name), exist_ok=True)
        self.save_xyz(name)
        atoms = read(name)
        os.remove(name)
        return atoms


if __name__ == "__main__":
    from ff_energy.utils.ffe_utils import read_from_pickle
    from ff_energy.ffe.constants import PKL_PATH, FFEPATH

    dcm_ = next(read_from_pickle(PKL_PATH / "structures" / "dcm.pkl"))
    test_obj = dcm_[0][0]

    test_obj.read_pdb(FFEPATH / test_obj.path)
    test_obj.set_2body()
    print(test_obj.pairs)
