from brain.adaptive_learning import AdaptiveLearning
al = AdaptiveLearning()
adapt = al.get_adaptations()
print(f"Win rate:           {adapt.get('win_rate', 'N/A')}")
print(f"Selectivity offset: {adapt.get('selectivity_offset', 0)}")
print(f"Lot multiplier:     {adapt.get('lot_multiplier', 1.0)}")
