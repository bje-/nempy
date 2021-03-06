## nempy
nempy is a set of tools that allow the user to model the dispatch procedure used in Australia's National Electricty 
Market. The idea is that you can start simple, like in the example below, and grow the complexity of your model by adding 
features such as ramping constraints, interconnectors and FCAS markets. Not all these feature are available yet, see 
the examples to get an idea of what it can do already.

## In development
No stable version released yet.

## Install
Not added to pypi yet, you need to download the source to use.

## Documentation
Find it on [readthedocs](https://nempy.readthedocs.io/en/latest/)

## A simple example
```python
import pandas as pd
from nempy import markets

# Volume of each bid, number of bands must equal number of bands in price_bids.
volume_bids = pd.DataFrame({
    'unit': ['A', 'B'],
    '1': [20.0, 50.0],  # MW
    '2': [20.0, 30.0],  # MW
    '3': [5.0, 10.0]  # More bid bands could be added.
})

# Price of each bid, bids must be monotonically increasing.
price_bids = pd.DataFrame({
    'unit': ['A', 'B'],
    '1': [50.0, 50.0],  # $/MW
    '2': [60.0, 55.0],  # $/MW
    '3': [100.0, 80.0]  # . . .
})

# Other unit properties
unit_info = pd.DataFrame({
    'unit': ['A', 'B'],
    'region': ['NSW', 'NSW'],  # MW
})

# The demand in the region\s being dispatched
demand = pd.DataFrame({
    'region': ['NSW'],
    'demand': [120.0]  # MW
})

# Create the market model
simple_market = markets.Spot(dispatch_interval=5)
simple_market.set_unit_info(unit_info)
simple_market.set_unit_energy_volume_bids(volume_bids)
simple_market.set_unit_energy_bids(price_bids)
simple_market.set_demand_constraints(demand)

# Calculate dispatch and pricing
simple_market.dispatch()

# Return the total dispatch of each unit in MW.
print(simple_market.get_energy_dispatch())
#   unit  dispatch
# 0    A      40.0
# 1    B      80.0

# Return the price of energy in each region.
print(simple_market.get_energy_prices())
#   region  price
# 0    NSW   60.0
```
