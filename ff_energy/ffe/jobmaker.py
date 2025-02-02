import os.path
import os
from pathlib import Path
from multiprocessing.pool import Pool
from itertools import repeat
from tqdm import tqdm

from ff_energy.ffe.job import Job
from ff_energy.ffe.structure import Structure
from ff_energy.ffe.constants import atom_types, PDB_PATH
from ff_energy.logs.logging import logger


def get_structures_pdbs(PDBPATH, atom_types=atom_types, system_name=None):
    logger.info(f"Loading structures from {PDBPATH}")
    logger.info(f"Atom types: {atom_types}")
    logger.info(f"System name: {system_name}")

    structures = []
    if not isinstance(PDBPATH, Path):
        PDBPATH = Path(PDBPATH)
    if not PDBPATH.is_absolute():
        PDBPATH = PDB_PATH / PDBPATH

    pdbs = [_ for _ in PDBPATH.glob("*.pdb")]
    for p in pdbs:
        s_path = PDBPATH / p
        s = Structure(s_path, _atom_types=atom_types, system_name=system_name)
        _ = s.get_pdb()
        # s.set_2body()
        structures.append(s)

    return structures, pdbs


class JobMaker:
    def __init__(self, jobdir, pdbs, structures, kwargs, RES=None):
        self.pdbs = pdbs
        self.jobdir = jobdir
        self.structures = structures
        self.kwargs = kwargs
        self.molpro_jobs = {}
        self.charmm_jobs = {}
        self.coloumb_jobs = {}
        self.data = []
        self.RES = RES

    def loop(self, func, args, **kwargs):
        # Create a thread pool
        pool = Pool(processes=2)  # multiprocessing.Semaphore(4)
        # Start the jobs.py
        pool.starmap(
            func,
            tqdm(zip(self.pdbs, self.structures, repeat(args)), total=len(self.pdbs)),
        )
        # Close the pool and wait for the work to finish
        pool.close()
        pool.join()

    def get_cluster_jobs(self, homedir):
        jobs = []
        for p in self.pdbs:
            print(p)
            ID = p
            slurm_path = f"{homedir}/{self.jobdir}/{ID}/cluster/{ID}.sh"
            outfilename = f"{homedir}/{self.jobdir}/{ID}/cluster/{ID}.out"
            if os.path.exists(outfilename):
                if open(outfilename).read().find("Molpro calculation terminated") == -1:
                    jobs.append(slurm_path)
            else:
                jobs.append(slurm_path)
        return jobs

    def get_monomer_jobs(self, homedir):
        jobs = []
        for p in self.pdbs:
            ID = p.split(".")[0]
            monomers_path = f"{homedir}/{self.jobdir}/{ID}/monomers/"
            out_jobs = Path(monomers_path).glob(f"{ID}*sh")
            for outfilename in out_jobs:
                keep = True
                of = Path(str(outfilename)[:-3] + ".out")
                if of.exists():
                    if open(of).read().find("terminated"):
                        keep = False
                    else:
                        keep = True
                else:
                    keep = True
                if keep:
                    jobs.append(outfilename)
        return jobs

    def get_pairs_jobs(self, homedir):
        jobs = []
        for p in self.pdbs:
            ID = p.split(".")[0]
            monomers_path = f"{homedir}/{self.jobdir}/{ID}/pairs/"
            out_jobs = Path(monomers_path).glob(f"{ID}*sh")
            for outfilename in out_jobs:
                keep = True
                of = Path(str(outfilename)[:-3] + ".out")
                if of.exists():
                    if open(of).read().find("terminated"):
                        keep = False
                    else:
                        keep = True
                else:
                    keep = True
                if keep:
                    jobs.append(outfilename)
        return jobs

    def get_coloumb_jobs(self, homedir):
        jobs = []
        for p in self.pdbs:
            ID = p.split(".")[0]
            monomers_path = f"{homedir}/{self.jobdir}/{ID}/coloumb/"
            out_jobs = Path(monomers_path).glob(f"{ID}*sh")
            #  check to see if the job has already finished successfully
            for outfilename in out_jobs:
                keep = True
                of = Path(str(outfilename)[:-3] + ".py.out")
                if of.exists():
                    if open(of).read().find("kcal"):
                        keep = False
                    else:
                        keep = True
                else:
                    keep = True
                if keep:
                    jobs.append(outfilename)
        return jobs

    def get_charmm_jobs(self, homedir):
        jobs = []
        for p in self.pdbs:
            # ID = p.split(".")[0]
            ID = p
            print(ID)
            slurm_path = f"{homedir}/{self.jobdir}/{ID}/charmm/{ID}.slurm"
            jobs.append(slurm_path)
        return jobs

    def get_esp_view_jobs(self, homedir):
        jobs = []
        for p in self.pdbs:
            # ID = p.split(".")[0]
            ID = p
            print(ID)
            slurm_path = f"{homedir}/{self.jobdir}/{ID}/charmm/{ID}.slurm"
            jobs.append(slurm_path)
        return jobs

    def esp_view(self, homedir, chmdir):
        chmdir = f"{chmdir}/" "{}/charmm/"
        self.loop(self.make_esp_view, [homedir, chmdir])

    def gather_data(self, homedir, monomers, clusters, pairs, coloumb, charmm):
        monomers = f"{monomers}/" "{}/monomers/"
        clusters = f"{clusters}/" "{}/cluster/"
        coloumb = f"{coloumb}/" "{}/coloumb/"
        charmm = f"{charmm}/" "{}/charmm/"
        pairs = f"{pairs}/" "{}/pairs/"
        self.loop(
            self.make_data_job, [homedir, monomers, clusters, pairs, coloumb, charmm]
        )

    def make_charmm(self, homedir):
        self.loop(self.make_charmm_job, homedir)

    def make_molpro(self, homedir):
        self.loop(self.make_molpro_job, homedir)

    def make_coloumb(self, homedir, mp):
        self.loop(self.make_coloumb_job, [homedir, mp])

    def make_data_job(self, p, s, args):
        homedir, mp, cp, p_p, c_p, chm_p = args
        if isinstance(homedir, tuple):
            homedir = homedir[0]
        logger.info(f"Making data job for {p}")

        ID = str(Path(p).name)
        if ID.endswith(".pdb"):
            ID = ID[:-4]
        print(ID)

        j = Job(ID, f"{homedir}/{self.jobdir}/{ID}", s, kwargs=self.kwargs)
        j.gather_data(
            monomers_path=Path(mp.format(ID)),
            cluster_path=Path(cp.format(ID)),
            pairs_path=Path(p_p.format(ID)),
            coloumb_path=Path(c_p.format(ID)),
            chm_path=Path(chm_p.format(ID)),
        )

    def make_charmm_job(self, p, s, homedir):
        #  check if the homedir is a tuple
        if isinstance(homedir, tuple):
            homedir = homedir[0]
        if isinstance(p, str):
            ID = p.split(".")[0]
        elif isinstance(p, Path):
            ID = p.stem
        else:
            raise Exception(f"Unknown type for p *job id* {p}")
        j = Job(ID, f"{homedir}/{self.jobdir}/{ID}", s, kwargs=self.kwargs)
        j.generate_charmm(RES=self.RES)
        # self.charmm_jobs[ID] = j

    def make_esp_view(self, p, s, args):
        homedir, charm_path = args
        if isinstance(Path, p):
            ID = p.stem
        else:
            ID = p.split(".")[0]
        j = Job(ID, f"{homedir}/{self.jobdir}/{ID}", s, kwargs=self.kwargs)
        j.generate_esp_view(charmm_path=charm_path.format(ID))

    def make_coloumb_job(self, p, s, args):
        homedir, mp = args
        if isinstance(p, Path):
            ID = p.stem
        else:
            ID = p.split(".")[0]
        j = Job(ID, f"{homedir}/{self.jobdir}/{ID}", s, kwargs=self.kwargs)
        j.generate_coloumb_interactions(monomers_path=Path(mp.format(ID)))

    def make_molpro_job(self, p, s, homedir):
        if isinstance(homedir, tuple):
            homedir = homedir[0]
        if isinstance(p, str):
            ID = p.split(".")[0]
        elif str(p.name).endswith(".pdb"):
            ID = p.name[:-4]

        j = Job(ID, f"{homedir}/{self.jobdir}/{ID}", s, kwargs=self.kwargs)
        j.generate_molpro()
        self.molpro_jobs[ID] = j
