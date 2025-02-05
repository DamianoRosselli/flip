import sympy as sy
from sympy.printing import pycode
from sympy.physics import wigner
from sympy.simplify.fu import TR8
from sympy.polys.orthopolys import legendre_poly
import multiprocessing as mp
from flip.utils import create_log
import numpy as np
import itertools

log = create_log()


def simplify_term(
    term,
    simplification_method="simplify_iteration",
    max_simplification=20,
):
    _avail_simplification_methods = "simplify_iteration", "tr8_iteration"

    if simplification_method == "simplify_iteration":
        term_simplified = sy.simplify(term)
        i = 0
        while (term_simplified != term) & (i < max_simplification):
            term_simplified, term = (
                sy.factor(TR8(term_simplified)),
                term_simplified,
            )
            i += 1
    elif simplification_method == "tr8_iteration":
        term_simplified = sy.factor(TR8(term))
        i = 0
        while (term_simplified != term) & (i < max_simplification):
            term_simplified, term = (
                sy.factor(TR8(term_simplified)),
                term_simplified,
            )
            i += 1
    else:
        log.add(
            f"Simplification method {simplification_method} not available."
            f"Choose between: {_avail_simplification_methods}"
        )

    return term_simplified


def generate_MN_ab_i_l_function_wide_angle(
    term_B,
    l,
    l1,
    l2,
):
    theta, phi = sy.symbols("theta phi")
    mu1, mu2 = sy.symbols("mu1 mu2")
    integral_mu1_M_l = sy.integrate(term_B * legendre_poly(l1, x=mu1), (mu1, -1, 1))
    integral_mu1_mu2_M_l = sy.integrate(
        integral_mu1_M_l * legendre_poly(l2, x=mu2), (mu2, -1, 1)
    )
    term_N_l_l1_l2 = 0
    for m in range(-l, l + 1):
        for m1 in range(-l1, l1 + 1):
            for m2 in range(-l2, l2 + 1):
                term_N_l_l1_l2_m_m1_m2 = wigner.gaunt(l, l1, l2, m, m1, m2)
                term_N_l_l1_l2_m_m1_m2 *= (
                    sy.Ynm_c(l, m, sy.pi - phi, 0)
                    * sy.Ynm_c(l1, m1, theta / 2, sy.pi)
                    * sy.Ynm_c(l2, m2, theta / 2, 0)
                )
                term_N_l_l1_l2 = term_N_l_l1_l2 + term_N_l_l1_l2_m_m1_m2
    term_M_l_l1_l2 = (1 / sy.Rational(4)) * integral_mu1_mu2_M_l.expand(func=True)
    term_N_l_l1_l2 = (sy.Rational(4) * sy.pi) ** 2 * term_N_l_l1_l2.expand(func=True)
    term_M_l_l1_l2 = simplify_term(
        term_M_l_l1_l2,
        simplification_method="simplify_iteration",
    )
    term_N_l_l1_l2 = simplify_term(
        term_N_l_l1_l2,
        simplification_method="tr8_iteration",
    )

    return term_M_l_l1_l2, term_N_l_l1_l2


def generate_MN_ab_i_l_function_parallel_plane(term_B, l):
    phi = sy.symbols("phi")
    mu = sy.symbols("mu")
    M_l = sy.Rational((2 * l + 1) / 2) * sy.integrate(
        term_B * legendre_poly(l, x=mu), (mu, -1, 1)
    )
    N_l = legendre_poly(l, x=sy.cos(phi))
    M_l = simplify_term(
        M_l.expand(func=True),
        simplification_method="simplify_iteration",
    )
    N_l = simplify_term(
        N_l.expand(func=True),
        simplification_method="tr8_iteration",
    )
    return M_l, N_l


def write_output(
    filename,
    type_list,
    term_index_list,
    lmax_list,
    output_pool,
    index_pool,
    wide_angle,
    additional_parameters=None,
    l1max_list=None,
    l2max_list=None,
    multi_index_model=False,
):
    f = open(filename, "w")
    f.write("import numpy as np\n")
    f.write("import scipy\n")
    f.write("\n")
    f.write("\n")
    dict_terms = {}
    dict_lmax = {}
    dict_j = {}
    for k, type in enumerate(type_list):
        dict_terms[f"{type}"] = term_index_list[k]
        dict_lmax[f"{type}"] = lmax_list[k]
        for i, t in enumerate(term_index_list[k]):
            for l in range(lmax_list[k][i] + 1):
                list_M_ab_i_l = []
                list_N_ab_i_l = []
                if wide_angle:
                    for l1 in range(l1max_list[k][i] + 1):
                        for l2 in range(l2max_list[k][i] + 1):
                            M_ab_i_l_l1_l2, N_ab_i_l_l1_l2 = output_pool[
                                index_pool[f"{type}_{t}_{l}_{l1}_{l2}"]
                            ]
                            if (M_ab_i_l_l1_l2 != 0) & (N_ab_i_l_l1_l2 != 0):
                                list_M_ab_i_l.append(M_ab_i_l_l1_l2)
                                list_N_ab_i_l.append(N_ab_i_l_l1_l2)
                else:
                    M_ab_i_l_l1_l2, N_ab_i_l_l1_l2 = output_pool[
                        index_pool[f"{type}_{t}_{l}"]
                    ]
                    if (M_ab_i_l_l1_l2 != 0) & (N_ab_i_l_l1_l2 != 0):
                        list_M_ab_i_l.append(M_ab_i_l_l1_l2)
                        list_N_ab_i_l.append(N_ab_i_l_l1_l2)
                dict_j[f"{type}_{t}_{l}"] = len(list_M_ab_i_l)
                for j in range(len(list_M_ab_i_l)):
                    M_ab_i_l_j = (
                        pycode(list_M_ab_i_l[j])
                        .replace("math.erf", "scipy.special.erf")
                        .replace("math.", "np.")
                    )
                    N_ab_i_l_j = (
                        pycode(list_N_ab_i_l[j])
                        .replace("math.erf", "scipy.special.erf")
                        .replace("math.", "np.")
                    )

                    additional_str = ""
                    if additional_parameters is not None:
                        for add in additional_parameters:
                            additional_str = additional_str + f"{add},"
                    additional_str = additional_str[:-1]
                    f.write(f"def M_{type}_{t}_{l}_{j}({additional_str}):\n")
                    f.write(f"    def func(k):\n")
                    f.write(f"        return({M_ab_i_l_j})\n")
                    f.write(f"    return(func)\n")
                    f.write("\n")

                    f.write(f"def N_{type}_{t}_{l}_{j}(theta,phi):\n")
                    f.write(f"    return({N_ab_i_l_j})\n")
                    f.write("\n")

    f.write("dictionary_terms = ")
    f.write(repr(dict_terms))
    f.write("\n")

    f.write("dictionary_lmax = ")
    f.write(repr(dict_lmax))
    f.write("\n")

    f.write("dictionary_subterms = ")
    f.write(repr(dict_j))
    f.write("\n")

    f.write(f"multi_index_model = {multi_index_model}")
    f.write("\n")

    f.close()


def write_M_N_functions(
    filename,
    type_list,
    term_index_list,
    lmax_list,
    dict_B,
    additional_parameters=None,
    number_worker=1,
    wide_angle=False,
    l1max_list=None,
    l2max_list=None,
    multi_index_model=False,
):
    params_pool = []
    index_pool = {}
    index = 0
    for k, type in enumerate(type_list):
        for i, t in enumerate(term_index_list[k]):
            for l in range(lmax_list[k][i] + 1):
                B_ab_i = dict_B[f"B_{type}_{t}"]
                if wide_angle:
                    for l1 in range(l1max_list[k][i] + 1):
                        for l2 in range(l2max_list[k][i] + 1):
                            params_pool.append([B_ab_i, l, l1, l2])
                            index_pool[f"{type}_{t}_{l}_{l1}_{l2}"] = index
                            index = index + 1
                else:
                    params_pool.append([B_ab_i, l])
                    index_pool[f"{type}_{t}_{l}"] = index
                    index = index + 1

    if number_worker == 1:
        if wide_angle:
            output_pool = [
                generate_MN_ab_i_l_function_wide_angle(*param) for param in params_pool
            ]
        else:
            output_pool = [
                generate_MN_ab_i_l_function_parallel_plane(*param)
                for param in params_pool
            ]
    else:
        if wide_angle:
            with mp.Pool(number_worker) as pool:
                output_pool = pool.starmap(
                    generate_MN_ab_i_l_function_wide_angle, params_pool
                )
        else:
            with mp.Pool(number_worker) as pool:
                output_pool = pool.starmap(
                    generate_MN_ab_i_l_function_parallel_plane, params_pool
                )

    write_output(
        filename,
        type_list,
        term_index_list,
        lmax_list,
        output_pool,
        index_pool,
        wide_angle,
        additional_parameters=additional_parameters,
        l1max_list=l1max_list,
        l2max_list=l2max_list,
        multi_index_model=multi_index_model,
    )


def generate_generalized_adamsblake20_functions(
    filename="./adamsblake20/flip_terms.py", number_worker=8
):
    mu = sy.symbols("mu")
    k = sy.symbols("k", positive=True, finite=True, real=True)
    sig_g = sy.symbols("sig_g", positive=True, finite=True, real=True)
    type_list = ["gg", "gg", "gg"] + ["gv", "gv"] + ["vv"]
    type_list = ["gg", "gv", "vv"]
    term_index_list = [["0", "1", "2"], ["0", "1"], ["0"]]
    # lmax_list = [[4, 4, 4], [3, 3], [2]] # lmax list to stick to AD20
    # lmax_list = [[6, 6, 6], [5, 5], [2]] # lmax list to generate lmax + 1
    lmax_list = [[4, 4, 4], [3, 3], [2]]
    dict_B = {
        "B_gg_0": sy.exp(-((k * sig_g * mu) ** 2)),
        "B_gg_1": 2 * mu**2 * sy.exp(-((k * sig_g * mu) ** 2)),
        "B_gg_2": mu**4 * sy.exp(-((k * sig_g * mu) ** 2)),
        "B_gv_0": 100 * (mu / k) * sy.exp(-((k * sig_g * mu) ** 2) / 2),
        "B_gv_1": 100 * (mu**3 / k) * sy.exp(-((k * sig_g * mu) ** 2) / 2),
        "B_vv_0": 100**2 * mu**2 / k**2,
    }

    write_M_N_functions(
        filename,
        type_list,
        term_index_list,
        lmax_list,
        dict_B,
        additional_parameters=["sig_g"],
        number_worker=number_worker,
        wide_angle=False,
    )


def generate_generalized_lai22_functions(
    filename="./lai22/flip_terms.py", number_worker=8
):
    mu1, mu2 = sy.symbols("mu1 mu2")
    k = sy.symbols("k", positive=True, finite=True, real=True)

    # gg
    term_index_list_gg = []
    lmax_list_gg = []
    l1max_list_gg = []
    l2max_list_gg = []

    pmax_gg, qmax_gg = 3, 3
    p_index = np.arange(pmax_gg + 1)
    q_index = np.arange(qmax_gg + 1)
    m_index_gg = np.arange(0, (qmax_gg + pmax_gg) + 1)
    iter_pq = np.array(list(itertools.product(p_index, q_index)))
    sum_iter_pq = np.sum(iter_pq, axis=1)
    dict_B = {}
    for i in ["0", "1", "2"]:
        for m_value in m_index_gg:
            pq_index = iter_pq[sum_iter_pq == m_value]
            term_index_list_gg.append(f"{i}_{m_value}")
            if i == "0":
                lmax_list_gg.append(2 * m_value)
                l1max_list_gg.append(min(2 * m_value, 2 * pmax_gg))
                l2max_list_gg.append(min(2 * m_value, 2 * qmax_gg))
            elif i == "1":
                lmax_list_gg.append(2 * (m_value + 1))
                l1max_list_gg.append(min(2 * (m_value + 1), 2 * (pmax_gg + 1)))
                l2max_list_gg.append(min(2 * (m_value + 1), 2 * (qmax_gg + 1)))
            elif i == "2":
                lmax_list_gg.append(2 * (m_value + 2))
                l1max_list_gg.append(min(2 * (m_value + 1), 2 * (pmax_gg + 1)))
                l2max_list_gg.append(min(2 * (m_value + 1), 2 * (qmax_gg + 1)))

            B_gg_i = 0
            for pq in pq_index:
                p, q = pq[0], pq[1]

                if i == "0":
                    add = 1
                elif i == "1":
                    add = mu1**2 + mu2**2
                elif i == "2":
                    add = mu1**2 * mu2**2
                B_gg_i = (
                    B_gg_i
                    + (
                        (-1) ** (p + q)
                        / (2 ** (p + q) * sy.factorial(p) * sy.factorial(q))
                    )
                    * k ** (2 * (p + q))
                    * mu1 ** (2 * p)
                    * mu2 ** (2 * q)
                    * add
                )
                dict_B[f"B_gg_{i}_{m_value}"] = B_gg_i

    # gv
    term_index_list_gv = []
    lmax_list_gv = []
    l1max_list_gv = []
    l2max_list_gv = []

    pmax_gv = 3
    m_index_gv = np.arange(pmax_gv + 1)

    for i in ["0", "1"]:
        for m_value in m_index_gv:
            term_index_list_gv.append(f"{i}_{m_value}")
            l2max_list_gv.append(1)
            B_gv_i = 0
            if i == "0":
                add = 1
                lmax_list_gv.append(2 * m_value + 1)
                l1max_list_gv.append(2 * m_value)
            elif i == "1":
                add = mu1**2
                lmax_list_gv.append(2 * m_value + 3)
                l1max_list_gv.append(2 * m_value + 2)
            B_gv_i = (
                B_gv_i
                + ((-1) ** (m_value) / (2 ** (m_value) * sy.factorial(m_value)))
                * k ** (2 * m_value - 1)
                * mu1 ** (2 * m_value)
                * mu2
                * add
            )
            dict_B[f"B_gv_{i}_{m_value}"] = 100 * B_gv_i

    # vv
    lmax_list_vv = [2]
    l1max_list_vv = [1]
    l2max_list_vv = [1]
    term_index_list_vv = ["0_0"]
    dict_B["B_vv_0_0"] = 100**2 * mu1 * mu2 / k**2

    type_list = ["gg", "gv", "vv"]
    term_index_list = [term_index_list_gg, term_index_list_gv, term_index_list_vv]
    lmax_list = [lmax_list_gg, lmax_list_gv, lmax_list_vv]
    l1max_list = [l1max_list_gg, l1max_list_gv, l1max_list_vv]
    l2max_list = [l2max_list_gg, l2max_list_gv, l2max_list_vv]

    write_M_N_functions(
        filename,
        type_list,
        term_index_list,
        lmax_list,
        dict_B,
        additional_parameters=None,
        number_worker=number_worker,
        wide_angle=True,
        l1max_list=l1max_list,
        l2max_list=l2max_list,
        multi_index_model=True,
    )


def generate_generalized_carreres23_functions(
    filename="./carreres23/flip_terms.py", number_worker=8
):
    mu1, mu2 = sy.symbols("mu1 mu2")
    k = sy.symbols("k", positive=True, finite=True, real=True)
    type_list = ["vv"]
    term_index_list = [["0"]]
    lmax_list = [[2]]
    l1max_list = [[1]]
    l2max_list = [[1]]
    dict_B = {"B_vv_0": 100**2 * mu1 * mu2 / k**2}

    write_M_N_functions(
        filename,
        type_list,
        term_index_list,
        lmax_list,
        dict_B,
        number_worker=number_worker,
        wide_angle=True,
        l1max_list=l1max_list,
        l2max_list=l2max_list,
    )


def generate_generalized_ravouxcarreres_functions(
    filename="./ravouxcarreres/flip_terms.py", number_worker=8
):
    mu1, mu2 = sy.symbols("mu1 mu2")
    k = sy.symbols("k", positive=True, finite=True, real=True)
    sig_g = sy.symbols("sig_g", positive=True, finite=True, real=True)
    type_list = ["gg", "gv", "vv"]
    term_index_list = [["0", "1", "2"], ["0", "1"], ["0"]]
    # lmax_list = [[4, 4, 4], [3, 3], [2]] # Lists to follow the logic of AD20
    # l1max_list = [[2, 2, 2] , [2, 2] , [1]]
    # l2max_list = [[2, 2, 2] , [1, 1] , [1]]
    # lmax_list = [[6, 6, 6] , [5, 5] , [2]] # Lists to generate the model lmax + 1
    # l1max_list = [[4, 4, 4] , [4, 4] , [1]]
    # l2max_list = [[4, 4, 4] , [1, 1] , [1]]
    lmax_list = [[6, 6, 6], [5, 5], [2]]
    l1max_list = [[4, 4, 4], [4, 4], [1]]
    l2max_list = [[4, 4, 4], [1, 1], [1]]
    dict_B = {
        "B_gg_0": sy.exp(-((k * sig_g) ** 2) * (mu1**2 + mu2**2) / 2),
        "B_gg_1": (mu1**2 + mu2**2)
        * sy.exp(-((k * sig_g) ** 2) * (mu1**2 + mu2**2) / 2),
        "B_gg_2": (mu1**2 * mu2**2)
        * sy.exp(-((k * sig_g) ** 2) * (mu1**2 + mu2**2) / 2),
        "B_gv_0": 100 * (mu2 / k) * sy.exp(-((k * sig_g * mu1) ** 2) / 2),
        "B_gv_1": 100 * (mu2 * mu1**2 / k) * sy.exp(-((k * sig_g * mu1) ** 2) / 2),
        "B_vv_0": 100**2 * mu1 * mu2 / k**2,
    }

    write_M_N_functions(
        filename,
        type_list,
        term_index_list,
        lmax_list,
        dict_B,
        additional_parameters=["sig_g"],
        number_worker=number_worker,
        wide_angle=True,
        l1max_list=l1max_list,
        l2max_list=l2max_list,
    )


def generate_files():
    generate_generalized_carreres23_functions()
    generate_generalized_adamsblake20_functions()
    generate_generalized_lai22_functions()
    generate_generalized_ravouxcarreres_functions()
