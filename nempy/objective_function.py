import pandas as pd
from nempy import helper_functions as hf


def bids(variable_ids, price_bids):
    """Create the cost coefficients of energy in bids in the objective function.

    This function defines the cost associated with each decision variable that represents a unit's energy bid. Costs are
    are with reference to the regional node.

    Parameters
    ----------
    variable_ids : pd.DataFrame
        Variable ids with unit and capacity band information so costs can be assigned to correct decision variables.

        =============  ===============================================================
        Columns:       Description:
        unit           unique identifier of a dispatch unit (as `str`)
        service   the service being provided, optional, if missing energy assumed
                  (as `str`)
        capacity_band  the bid band of the variable (as `str`)
        variable_id    the id of the variable (as `int`)
        =============  ===============================================================

    price_bids : pd.DataFrame
        Bids by unit, in $/MW, can contain up to n bid bands.

        ========  ======================================================
        Columns:  Description:
        unit      unique identifier of a dispatch unit (as `str`)
        1         bid price in the 1st band, in $/MW (as `float`)
        2         bid price in the 2nd band, in $/MW (as `float`)
        n         bid price in the nth band, in $/MW (as `float`)
        ========  ======================================================

    Returns
    -------
    pd.DataFrame

        =============  ===============================================================
        Columns:       Description:
        unit           unique identifier of a dispatch unit (as `str`)
        capacity_band  the bid band of the variable (as `str`)
        variable_id    the id of the variable (as `int`)
        cost           the bid cost of the variable (as `float`)
        =============  ===============================================================
    """
    # If no service column is provided assume bids are for energy.
    if 'service' not in price_bids.columns:
        price_bids['service'] = 'energy'

    # Get the list of columns that are bid bands.
    bid_bands = [col for col in price_bids.columns if col not in ['unit', 'service']]
    price_bids = hf.stack_columns(price_bids, cols_to_keep=['unit', 'service'], cols_to_stack=bid_bands,
                                  type_name='capacity_band', value_name='cost')
    # Match bid cost with existing variable ids
    price_bids = price_bids[price_bids['cost'] != 0.0]
    objective_function = pd.merge(variable_ids, price_bids, how='inner', on=['unit', 'service', 'capacity_band'])
    return objective_function


def scale_by_loss_factors(objective_function, unit_info):
    """
    Scale the bid cost by dividing by the loss factor.

    Parameters
    ----------
    objective_function : pd.DataFrame
        Cost by variable id, also including unit and capacity band so loss factors can be applied if provided.

        =============  ===============================================================
        Columns:       Description:
        unit           unique identifier of a dispatch unit (as `str`)
        capacity_band  the bid band of the variable (as `str`)
        variable_id    the id of the variable (as `int`)
        =============  ===============================================================

    unit_info : pd.DataFrame
        The loss factor to scale bids by.

        =============  ===============================================================
        Columns:       Description:
        unit           unique identifier of a dispatch unit (as `str`)
        loss_factor    the id of the variable (as `int`)
        =============  ===============================================================

    Returns
    -------
    pd.DataFrame

        =============  ===============================================================
        Columns:       Description:
        unit           unique identifier of a dispatch unit (as `str`)
        capacity_band  the bid band of the variable (as `str`)
        variable_id    the id of the variable (as `int`)
        cost           the bid cost of the variable (as `float`)
        =============  ===============================================================
    """

    # Match units with their loss factors.
    objective_function = pd.merge(objective_function, unit_info, how='inner', on='unit')
    # Refer bids cost to regional reference node, if a loss factor  was provided.
    objective_function['cost'] = objective_function['cost'] / objective_function['loss_factor']
    return objective_function
