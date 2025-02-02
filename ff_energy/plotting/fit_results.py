from ff_energy.utils.ffe_utils import pickle_output, read_from_pickle, str2int, PKL_PATH
from ff_energy.utils.json_utils import load_json
from pathlib import Path
import pandas as pd
import jax.numpy as jnp
import itertools as it
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import patchworklib as pw


def residuals_from_keys(df, k1, k2,
                        xlabel=None, ylabel=None,
                        label="", title="", LABEL_SIZE=10):
    #  make the dataframe
    df_test = pd.DataFrame(
        {
            "target": df[k1],
            "residuals": df[k1] - df[k2],
            "vals": df[k2]
        }
    ).dropna()  # drop the nans
    residuals_plot(df_test, label, title, LABEL_SIZE, xlabel, ylabel)


def residuals_plot(df_test, label,
                   title="", LABEL_SIZE=10,
                   xlabel=None, ylabel=None):
    if xlabel is None:
        xlabel = "target"
    if ylabel is None:
        ylabel = "observation"

    #  color by residuals
    cmap = sns.color_palette("coolwarm", as_cmap=True)
    norm = plt.Normalize(df_test["residuals"].min(),
                         df_test["residuals"].max())
    normabs = plt.Normalize(abs(df_test["residuals"]).min(),
                            abs(df_test["residuals"]).max())

    pw.overwrite_axisgrid()
    FIGSIZE = (3, 3)
    TITLE_SIZE = 10

    target_mean = df_test["target"].mean()
    residuals_mean = df_test["residuals"].mean()
    vals_mean = df_test["vals"].mean()
    target_sd = df_test["target"].std()
    residuals_sd = df_test["residuals"].std()
    vals_sd = df_test["vals"].std()
    target_max = df_test["target"].max()
    residuals_max = df_test["residuals"].max()
    vals_max = df_test["vals"].max()
    target_min = df_test["target"].min()
    residuals_min = df_test["residuals"].min()
    vals_min = df_test["vals"].min()

    RMSE = np.sqrt(np.mean(df_test["residuals"] ** 2))
    MAE = np.mean(np.abs(df_test["residuals"]))
    r2 = np.corrcoef(df_test["target"], df_test["vals"])[0, 1] ** 2

    bounds = (np.min([target_min, vals_min, ]),
              np.max([target_max, vals_max, ]))

    g1 = sns.jointplot(data=df_test, x="target", y="vals",
                       ratio=3, marginal_ticks=True,
                       kind="reg", marker="+")
    g1.plot_joint(sns.kdeplot, color="r", zorder=0, levels=6)
    g1.plot_marginals(sns.rugplot, color="r", height=-.15, clip_on=True)
    g1.ax_joint.plot([bounds[0], bounds[1]],
                     [bounds[0], bounds[1]], 'k--', linewidth=2)
    g1.ax_marg_x.axvline(x=target_mean, c="k", linestyle="--")
    g1.ax_marg_y.axhline(y=vals_mean, c="k", linestyle="--")

    # JointGrid has a convenience function
    g1.set_axis_labels(xlabel, ylabel, fontsize=16, fontweight='bold')

    # # or set labels via the axes objects
    # h.ax_joint.set_xlabel('new x label', fontweight='bold')

    analysis_string = f"RMSE: {RMSE:.2f}\nMAE: {MAE:.2f}\nR2: {r2:.2f}"
    g1.ax_joint.text(0.25, 0.8, analysis_string,
                     horizontalalignment='center', c="black",
                     bbox=dict(facecolor='white', alpha=0.5),
                     transform=g1.ax_joint.transAxes,
                     fontdict={"size": LABEL_SIZE}
                     )
    g1 = pw.load_seaborngrid(g1, label="g1", figsize=FIGSIZE)

    g2 = sns.jointplot(data=df_test, x="target", y="residuals",
                       ratio=3, marginal_ticks=True,
                       kind="reg", marker="+")
    g2.plot_joint(sns.kdeplot, color="r", zorder=0, levels=6)
    g2.plot_marginals(sns.rugplot, color="r", height=-.15, clip_on=True)
    g2.ax_joint.axhline(y=0, color="k", linestyle="--")

    g2.set_axis_labels(xlabel, "residuals", fontsize=16, fontweight='bold')

    g2 = pw.load_seaborngrid(g2, label="g2", figsize=FIGSIZE)

    g3 = sns.jointplot(data=df_test, x="residuals", y="vals",
                       ratio=3, marginal_ticks=True,
                       kind="reg", marker="+")
    g3.plot_joint(sns.kdeplot, color="r", zorder=0, levels=6)

    g3.set_axis_labels("residuals", ylabel, fontsize=16, fontweight='bold')

    g3.plot_marginals(sns.rugplot, color="r", height=-.15, clip_on=True)
    g3.ax_joint.axvline(x=0, color="k", linestyle="--")
    g3 = pw.load_seaborngrid(g3, label="g3", figsize=FIGSIZE)

    distax = pw.Brick(figsize=(FIGSIZE[0], FIGSIZE[1] * 3 / 4))
    distax.set_title(title)
    _ = sns.kdeplot(data=df_test, x="target", color="blue",
                    ax=distax, label="target")
    _ = sns.kdeplot(data=df_test, x="vals", color="red",
                    ax=distax, label="fit")

    val_string = f"Fit\nmean: {vals_mean:.2f}\nstd: {vals_sd:.1f}"
    distax.text(0.05, 0.8, val_string,
                horizontalalignment='left', c="red",
                bbox=dict(facecolor='white', alpha=0.5),
                transform=distax.transAxes,
                fontdict={"size": LABEL_SIZE})

    distax.set_xlabel(xlabel)

    target_string = f"Target\nmean: {target_mean:.2f}\nstd: {target_sd:.1f}"
    distax.text(0.05, 0.6, target_string,
                horizontalalignment='left', c="blue",
                bbox=dict(facecolor='white', alpha=0.5),
                transform=distax.transAxes,
                fontdict={"size": LABEL_SIZE})

    x_vals = np.zeros(len(df_test) * 2)
    y_vals = np.zeros(len(df_test) * 2)
    x_vals[0::2] = df_test["target"]
    x_vals[1::2] = df_test["vals"]
    y_vals[1::2] = [1] * len(df_test)

    para = pw.Brick(figsize=(FIGSIZE[0], FIGSIZE[1] / 4))
    for i in range(len(df_test)):
        res = df_test["residuals"].iloc[i]
        normed = norm(res)
        c = cmap(normed)
        alph = normabs(abs(res))
        distax.plot(
            x_vals[i * 2:i * 2 + 2],
            y_vals[i * 2:i * 2 + 2],
            alpha=alph * 0.5,
            c=c
        )
    para.set_yticks([])
    para.set_ylabel("")
    para.set_xlabel("Value")
    para.set_title("Change", loc="center")

    print("saving ", label)
    rt = distax
    g1.case.set_title('A. Regression', x=1.0, y=1.0, loc="right")
    rt.case.set_title('B. Distribution learning', x=1.0, y=1.0, loc="right")
    g2.case.set_title('C. Residuals vs. ground truth', x=1.0, y=1.0, loc="right")
    g3.case.set_title('D. Residuals vs. fit', x=1.0, y=1.0, loc="right")

    final_plot = ((g1 | rt) / (g2 | g3))
    final_plot.set_suptitle(label, loc="left", fontsize=TITLE_SIZE)
    final_plot.savefig(f"{label}.png", bbox_inches="tight")


from sklearn.metrics import mean_squared_error as calc_rmse
from sklearn.metrics import mean_absolute_percentage_error as calc_mape
import scipy
from matplotlib.ticker import MaxNLocator
from scipy.stats import gaussian_kde
from matplotlib.ticker import FormatStrFormatter


def simple_residuals_plot(df_test, label,
                          title="", LABEL_SIZE=10,
                          xlabel=None, ylabel=None,
                          bottomLeft=True, resColor=False,
                          KDE=False):
    if xlabel is None:
        xlabel = "target"
    if ylabel is None:
        ylabel = "observation"

    #  color by residuals
    cmap = sns.color_palette("coolwarm", as_cmap=True)
    norm = plt.Normalize(df_test["residuals"].min(),
                         df_test["residuals"].max())
    normabs = plt.Normalize(abs(df_test["residuals"]).min(),
                            abs(df_test["residuals"]).max())

    pw.overwrite_axisgrid()

    FIGSIZE = (3, 3)
    TITLE_SIZE = 10

    targets = df_test["target"]
    values = df_test["vals"]

    target_mean = df_test["target"].mean()
    residuals_mean = df_test["residuals"].mean()
    vals_mean = df_test["vals"].mean()
    target_sd = df_test["target"].std()
    residuals_sd = df_test["residuals"].std(ddof=0)
    vals_sd = df_test["vals"].std()
    target_max = df_test["target"].max()
    residuals_max = df_test["residuals"].max()
    vals_max = df_test["vals"].max()
    target_min = df_test["target"].min()
    residuals_min = df_test["residuals"].min()
    vals_min = df_test["vals"].min()

    RMSE = np.sqrt(np.mean(df_test["residuals"] ** 2))
    MAE = np.mean(np.abs(df_test["residuals"]))
    r2 = np.corrcoef(df_test["target"], df_test["vals"])[0, 1] ** 2

    bounds = (np.min([target_min, vals_min, ]),
              np.max([target_max, vals_max, ]))

    analysis_string = f"RMSE: {RMSE:.2f}\nMAE: {MAE:.2f}\nR2: {r2:.2f}"
    val_string = f"Fit\nmean: {vals_mean:.2f}\nstd: {vals_sd:.1f}"
    target_string = f"Target\nmean: {target_mean:.2f}\nstd: {target_sd:.1f}"

    """MIKES STYLE
    """
    rmseb = np.sqrt(calc_rmse(targets, values))
    MAE = np.mean(abs(targets - values))

    slopeb, interceptb, r_valueb, p_valueb, std_errb = scipy.stats.linregress(
        targets, values)

    gmin = min(np.min(targets), np.min(values))
    gmax = max(np.max(targets), np.max(values))

    cols = ['blue', 'red', 'green', 'orange', 'brown']
    axisFont = {'family': 'sans', 'weight': 'bold', 'size': 22}
    font1 = {'size': 15}
    font2 = {'size': 14}

    diax = [gmin, gmax]
    diay = [gmin, gmax]

    plot = pw.Brick(figsize=(FIGSIZE[0], FIGSIZE[1]))

    plot.tick_params(axis='both', which='major', labelsize=20)

    # Calculate the point density
    xy = np.vstack([targets, values])
    z = gaussian_kde(xy)(xy)

    # Sort the points by density, so that the densest points are plotted last
    idx = z.argsort()
    x, y, z = targets[idx], values[idx], z[idx]
    if resColor:
        z = df_test["residuals"][idx]
        plt.set_cmap("coolwarm")
    # plt.set_cmap("plasma")
    plot.scatter(x, y, marker=".", c=z, alpha=1.0)

    plot.plot([0, 1], [0, 1], c='gray', alpha=0.5, transform=plot.transAxes)

    # ax.legend(loc='upper left')
    plot.set_xlabel(f'{xlabel}', fontdict=axisFont)
    plot.set_ylabel(f'{ylabel}', fontdict=axisFont)
    if residuals_sd > rmseb:
        residuals_sd = rmseb
    analysis_string = \
        '$r^{2}$:' + f"{r_valueb ** 2 :6.2f}\n" \
        + 'RMSE:' + f"{rmseb :6.2f}\n" \
        + '$\sigma_{\mathrm{err.}}$:' f"{residuals_sd :6.2f}"

    if bottomLeft:
        xT = 0.95
        yT = 0.05
        ha = "right"
        va = "bottom"
    else:
        xT = 0.10
        yT = 0.90
        ha = "left"
        va = "top"

    plot.text(xT, yT, analysis_string,
              fontsize=20, color="k",
              alpha=0.5,
              horizontalalignment=ha,
              verticalalignment=va,
              transform=plot.transAxes)

    if KDE:
        sns.kdeplot(df_test, x="target", y="vals",
                    weights=abs(df_test["residuals"]),
                    levels=4,
                    ax=plot, alpha=0.55, c="k")
        pos = df_test[df_test["residuals"] > 0]
        pos_comX = np.average(pos["target"], weights=pos["residuals"])
        pos_comY = np.average(pos["vals"], weights=pos["residuals"])
        neg = df_test[df_test["residuals"] < 0]
        neg_comX = np.average(neg["target"], weights=neg["residuals"])
        neg_comY = np.average(neg["vals"], weights=neg["residuals"])
        # plot positive center of mass
        plot.scatter(pos_comX, pos_comY, marker="x", c="red",
                     linewidths=3.5,
                     alpha=0.75, s=100)
        # plot negative center of mass
        plot.scatter(neg_comX, neg_comY, marker="x", c="blue", alpha=0.75,
                     linewidths=3.5,
                     s=100)

    # analysis_string2 = 'Fit\nmean: %.2f' % vals_mean + '\nstd: %.1f' % vals_sd

    plot.set_xlim([gmin, gmax])
    plot.set_ylim([gmin, gmax])

    #  make the number of ticks consistent
    plot.xaxis.set_major_locator(MaxNLocator(4))
    plot.yaxis.set_major_locator(MaxNLocator(4))
    plot.xaxis.set_major_formatter(FormatStrFormatter('%4.0f'))
    plot.yaxis.set_major_formatter(FormatStrFormatter('%4.0f'))

    plot.set_title(label, x=0.15, y=0.8)

    return plot
