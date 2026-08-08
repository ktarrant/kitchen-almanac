# Goals
- A: Start with a "Wishlist" of vegetables that we want to grow in our garden
- B: Identify specific species/varieties of each that can be grown in our region
- C: Create a super detailed about how to grow each crop
- D: Use available planting space, seasonality, and user preference to generate a gardening plan for all crops for the year
- E: Estimate harvest times and yields of complete garden based on garden plan
- F: Create meal prep and preservation plans to utilize yields

# Ideas
- A: Start with a list of vegetables - basically each line is a search term
- B:
    - Search term from (A) is resolved into a set of likely species/varietals that fit that name
    - Varietals are filtered by suitability for our area
- C:
    - As detailed a guide as possible for growing that crop using the seed/start identified in (B)
    - Assume the user knows very little to nothing about gardening
    - Considerations for a backyard garden
    - Container vs garden bed, size of container or garden spacing
    - Starting seeds inside and then planting starts vs direct sow
    - Type of soil
    - amount of light
    - Is a trellis needed
    - Watering frequency, drought resistance
    - Plants that pair well together
    - Any other information
    - Create a timeline
        - When exactly to plant seeds/starts
        - When harvesting season starts/ends
- D:
    - User sets a preference for each crop based on presented data from (C)
    - User configures their available garden space, number of containers, size of containers
    - System allocates planting locations based on data from (C)
    - Combined garden instructions from each crop into a combined gardening timeline
- E:
    - Use data from (D) to compile an amount and timing of harvest yields
- F:
    - Use recipe data and data from (E) to portion out meal prep portions and preserves (fermenting, pickling) jar counts

# Data Sourcing
- I want each step to somewhat deterministic - as in, I want a script to be written to perform each step.
- We should use online sources as much as possible to build our guides:
    - Some search lookup for finding specific varietals for input produce names
    - Some website lookup for suitability of a crop in our region (USDA Hardiness Zone)
    - Some website to look up agriculture data about the varietal, ideally a full grow guide
        - Maybe an LLM step here to convert the information about the crop into an actual grow guide
    - Steps D, E, F should basically be fully deterministic - once we know each crops timeline and growing needs, as well as the user's preference and available planting space, there should be a deterministic optimum allocation

# Starting Point
As a starting point I created Six Seasons Reference, which lists seasonal vegetables by what time of year they are freshly harvested. It also contains some pantry info that can be ignored for now. I was thinking this vegetable list could be the starting point for our "Wishlist Vegetables". However it is based on a Mediterranean Climate, so not all vegetables may be good fits for our zone.
