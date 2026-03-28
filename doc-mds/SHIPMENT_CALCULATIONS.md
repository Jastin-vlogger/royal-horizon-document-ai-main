# Shipment Calculations Guide

This guide explains how we calculate shipment logistics from your LPO (Local Purchase Order) documents in simple terms.

## Glossary of Terms

| Term | What it means |
|------|---------------|
| **MT** | Metric Ton = 1,000 kilograms |
| **FCL** | Full Container Load = One complete shipping container |
| **20ft Container** | Standard small container that holds 25 MT |
| **40ft Container** | Standard large container that holds 26 MT |
| **Bag** | Individual package unit (e.g., one 40kg bag of rice) |
| **Pallet** | Wooden platform holding 50 bags |
| **UOM** | Unit of Measure (e.g., BAG/1x40kg means bags of 40kg each) |

## What We Calculate

From your LPO document, we automatically calculate:

1. **Container Size** - What size container you need (20ft or 40ft)
2. **Quantity in MT** - Total weight in metric tons
3. **FCL** - How many containers you need
4. **Bags** - Total number of bags
5. **Bags per Container** - How many bags fit in one container
6. **Pallets** - How many pallets you need
7. **FCL per Unit** - Price for one full container
8. **Price per MT** - Price for one metric ton

## Real Example from LPO

Let's use the example from your LPO document:

### What we have:
- **PO Number**: PO01/26/00117
- **Commodity**: Rice (PR11 Steam Rice - Indian Pride)
- **Quantity**: 15,000 bags
- **Packaging**: BAG/1x40kg (each bag weighs 40 kg)
- **Unit Price**: 22.40 per bag
- **Total Price**: 336,000.00

### Step-by-Step Calculations:

#### 1. Container Size
**Rule**: For rice, we use 20ft containers (this is the standard for rice shipments).

**Result**: Container Size = **20ft**

---

#### 2. Quantity in MT (Metric Tons)

**Formula**: 
```
Quantity in MT = (Number of bags × Weight per bag in kg) / 1000
```

**Calculation**:
```
= (15,000 bags × 40 kg) / 1000
= 600,000 kg / 1000
= 600 MT
```

**Result**: Quantity in MT = **600 MT**

---

#### 3. FCL (Full Container Load)

**What we know**:
- One 20ft container holds 25 MT
- We have 600 MT total

**Formula**:
```
FCL = Total MT / Container Capacity
(Round up to nearest whole number)
```

**Calculation**:
```
= 600 MT / 25 MT per container
= 24 containers
```

**Result**: FCL = **24 containers**

---

#### 4. Bags per Container

**What we know**:
- One 20ft container holds 25 MT = 25,000 kg
- Each bag weighs 40 kg

**Formula**:
```
Bags per Container = Container Capacity in kg / Weight per bag
```

**Calculation**:
```
= 25,000 kg / 40 kg per bag
= 625 bags
```

**Result**: Bags per Container = **625 bags**

---

#### 5. Pallets

**What we know**:
- Each pallet holds 50 bags (standard)
- We have 15,000 bags total

**Formula**:
```
Pallets = Total bags / 50
(Round up to nearest whole number)
```

**Calculation**:
```
= 15,000 bags / 50 bags per pallet
= 300 pallets
```

**Result**: Pallets = **300 pallets**

---

#### 6. FCL per Unit (Price per Container)

**What we know**:
- One container holds 625 bags
- Each bag costs 22.40

**Formula**:
```
FCL per Unit = Bags per container × Price per bag
```

**Calculation**:
```
= 625 bags × 22.40
= 14,000.00
```

**Result**: FCL per Unit = **14,000.00** (price for one full container)

---

#### 7. Price per MT (Price per Metric Ton)

**What we know**:
- Each bag weighs 40 kg
- Each bag costs 22.40

**Step 1**: Calculate how many bags make 1 MT
```
Bags per MT = 1,000 kg / 40 kg per bag
            = 25 bags
```

**Step 2**: Calculate price for 1 MT
```
Price per MT = Price per bag × Bags per MT
             = 22.40 × 25
             = 560.00
```

**Result**: Price per MT = **560.00**

---

## Summary Table for Example

| Calculation | Formula | Result |
|-------------|---------|--------|
| Container Size | Based on commodity (rice = 20ft) | 20ft |
| Quantity in MT | (15,000 × 40) / 1,000 | 600 MT |
| FCL | 600 / 25 | 24 containers |
| Bags | From LPO | 15,000 bags |
| Bags per Container | 25,000 / 40 | 625 bags |
| Pallets | 15,000 / 50 | 300 pallets |
| FCL per Unit | 625 × 22.40 | 14,000.00 |
| Price per MT | 22.40 × 25 | 560.00 |

## Different Packaging Examples

### Example 1: 10kg bags
- **Packaging**: 1X10KG
- **Bags per MT**: 1,000 / 10 = 100 bags
- **Bags per Container (20ft)**: 25,000 / 10 = 2,500 bags

### Example 2: 50kg bags
- **Packaging**: 1X50KG
- **Bags per MT**: 1,000 / 50 = 20 bags
- **Bags per Container (20ft)**: 25,000 / 50 = 500 bags

### Example 3: Multi-pack bags (4 x 10kg = 40kg)
- **Packaging**: 4X10KG
- **Total weight per unit**: 4 × 10 = 40 kg
- **Bags per MT**: 1,000 / 40 = 25 bags
- **Bags per Container (20ft)**: 25,000 / 40 = 625 bags

## Quick Reference: Container Standards

| Container Type | Capacity | Standard Use |
|----------------|----------|--------------|
| 20ft | 25 MT | Rice, Sugar (default) |
| 40ft | 26 MT | Large shipments |

**Note**: Currently, rice and sugar both use 20ft containers by default. This can be adjusted based on commodity type.

## What Happens if Data is Missing?

If any required field is missing from your LPO, the calculations will show `null` for fields that depend on it:

- **Missing packaging** → Cannot calculate quantity_in_mt, FCL, bags per container, price per MT
- **Missing quantity** → Cannot calculate quantity_in_mt, FCL, bags
- **Missing unit price** → Cannot calculate FCL per unit, price per MT
- **Missing commodity** → Container size will be null, FCL cannot be calculated

## How to Read the API Response

When you submit your LPO, you'll receive a JSON response with a `shipment_calculations` section:

```json
{
  "shipment_calculations": {
    "container_size": 20,
    "quantity_in_mt": 600.0,
    "fcl": 24,
    "bags": 15000,
    "bags_per_container": 625,
    "pallets": 300,
    "fcl_per_unit": 14000.0,
    "price_per_mt": 560.0
  }
}
```

Each field tells you:
- **container_size**: What size container to use (20 or 40)
- **quantity_in_mt**: Total weight of your shipment in metric tons
- **fcl**: How many containers you need to book
- **bags**: Total number of bags (from your LPO)
- **bags_per_container**: How many bags fit in each container
- **pallets**: How many pallets you need for storage/handling
- **fcl_per_unit**: What one full container costs
- **price_per_mt**: What one metric ton costs

## Common Questions

### Q: Why do we calculate FCL?
**A**: FCL tells you how many shipping containers you need to book with the shipping line. This is essential for logistics planning and cost estimation.

### Q: What if my quantity doesn't fill a full container?
**A**: We always round UP to the nearest whole container. For example, if you need 10.5 MT, you'll need 1 full container (which can hold 25 MT). The FCL will be 1.

### Q: Can I use 40ft containers instead of 20ft?
**A**: Currently, the system defaults to 20ft for rice and sugar. If you need 40ft containers, this can be configured based on your commodity type.

### Q: What if my bags are different sizes?
**A**: The system automatically detects the bag weight from the "UOM" or "Packaging" field in your LPO. It handles various formats like "10 Kg", "4X10KG", "BAG/1x40kg", etc.

### Q: How accurate are these calculations?
**A**: The calculations use industry-standard formulas and container capacities. They provide accurate estimates for planning purposes. Actual loading may vary slightly based on container configuration and stacking methods.

## Need Help?

If you see unexpected values or have questions about the calculations, check:
1. Is the packaging/UOM field correctly filled in your LPO?
2. Is the quantity field showing the correct number of bags?
3. Is the commodity field set to "Rice" or "Sugar"?

All calculations are automatic and based on the data extracted from your LPO document.
