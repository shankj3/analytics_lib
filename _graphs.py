import matplotlib
# fix
import matplotlib.pyplot as plt
import collections

def create_uniform_tcks(array):
    return [i for i in range(len(array))]


def create_degenerate_tcks(array):
    # http://stackoverflow.com/questions/22095746/scatter-plots-with-string-arrays-in-matplotlib#comment33515033_22096070
    arr_map = dict((sn, i) for i, sn in enumerate(set(array)))
    return [array[l] for l in array]


def create_useful_hist_xtcks_map(series):
    xtcks = range(len(series.unique()))
    hist_map = dict(zip(series.unique(), xtcks))
    return hist_map


def plot_string_2d(string_col, numeric_col, rotation, xtick_font_size=5, save_path=None):
    # plot a scatter 2d plot with a string column as x and numeric as y.
    fig, ax = plt.subplots(figsize=(20, 10))
    xticks = create_uniform_tcks(string_col)
    ax.scatter(x=xticks, y=numeric_col)
    plt.xlim([0,len(xticks)])
    plt.xticks(xticks)
    ax.set_xticklabels(string_col, rotation=rotation)
    for item in ax.get_xticklabels():
        item.set_fontsize(xtick_font_size)
    if save_path:
        plt.savefig(save_path)


def autolabel(rects, ax):
    # attach some text labels
    for rect in rects:
        height = rect.get_height()
        ax.text(rect.get_x() + rect.get_width()/2., 1.05*height,
                '%d' % int(height),
                ha='center', va='bottom')


def build_service_name_title(front_title, df):
    services = df.case_service_name.unique()
    if len(services) == 1:
        title_string = services[0]
    else:
        title_string = ', '.join(services)
    return front_title + title_string


def generic_scatter_over_plot(dataframes, x, y, labels, xtick_label=None, ytick_label=None, loc=None, save_name=None, style=None):
    """Generic scatter plotting.
       :param dataframes: dataframes to include in plot
       :type dataframes: list
       :param labels: Corresponding labels for creating legend
       :type labels: list
       :param x: x axis column of dataframe
       :type x: string
       :param y: y axis column of dataframe
       :type y: string
       :param xtick_label: If the plot data has been mapped to numbers from string values, provide column of string values here
       :type xtick_label: String
       :param ytick_label: Same as xtick_label
       :param loc: location of legend on plot
       :type loc: int
       :param save_name: if specified, location and name of plot to be saved
       :type save_name: string
    """
    if style:
        matplotlib.style.use('ggplot')
    fig, ax = plt.subplots(figsize=(20, 10))
    for dataframe, label in zip(dataframes, labels):
        ax.scatter(dataframe[x], dataframe[y], label=label, alpha=0.6)
    if loc:
        ax.legend(loc)
    else:
        ax.legend()
    if xtick_label:
        ax.set_xticklabels(xtick_label, rotation=70)
    if ytick_label:
        ax.set_yticklabels(ytick_label)
    if save_name:
        fig.save(save_name, bbox_inches='tight')
    else:
        fig.show()
    # this bs is a lot of if/else which is lame.


#
# def plot_coverage_by_endpoint(dataframe, mask, endpoint, title_str):
#   masked_df = dataframe[mask]
#   # there MUST BE A BETTER WAY
#   mapper = collections.OrderedDict()
#   u = 0
#   for end in masked_df[endpoint].unique():
#     mapper[case_action] = u
#     u+=1
#   fig, ax = plt.subplots(figsize=(20,10))
#   ax.hist(masked_df[endpoint].mask(mapper), bins=1.5*len(mapper), color='b', alpha=0.7)
#   ax.set_xticks(list(mapper.values()))
#   ax.set_xticklabels(list(mapper.keys()), rotation=70)
#   ax.set_title(title_str)