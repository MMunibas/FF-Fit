papermill templates/ff_template.ipynb out_notebooks/ff/epol_pairs_pbe0dz_pairs.ff.pkl.ipynb -k pycharmm -p ffpkl epol_pairs_pbe0dz_pairs.ff.pkl

jupyter nbconvert --to webpdf --no-input out_notebooks/ff/epol_pairs_pbe0dz_pairs.ff.pkl.ipynb
mv out_notebooks/ff/epol_pairs_pbe0dz_pairs.ff.pkl.pdf out_pdfs/qm
