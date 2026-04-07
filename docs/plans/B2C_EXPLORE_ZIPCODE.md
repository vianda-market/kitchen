# B2C Explore: City scope then zipcode search

**Status:** Not implemented (roadmap).

**Context:** The B2C restaurant explorer currently supports exploring by **city** (dropdown of cities within a country, then list/map of restaurants in that city). See [RESTAURANTS_BY_ZIPCODE.md](../api/b2c_client/feedback_from_client/RESTAURANTS_BY_ZIPCODE.md) and the implemented endpoints `GET /restaurants/cities` and `GET /restaurants/by-city`.

**Future enhancement:** Down the line, the product may allow users to scope the explore UI to a **city** and then refine the search by **zipcode** within that city. For example: user selects "Buenos Aires", then optionally selects or types a zipcode to see only restaurants in that area.

**Implementation note:** This would follow the same pattern as the city explorer: a `GET /restaurants/by-zipcode?zip=...&country_code=...` (and optionally `city=...` for scoping) endpoint, with route registered before `GET /{restaurant_id}`, returning restaurants with name, cuisine, and geolocation for list/map.
