# Local SEO Checklist

Reference guide for auditing local and SME business websites.

## Structured Data

- [ ] LocalBusiness JSON-LD schema (or a specific subtype such as Restaurant, Plumber, Dentist, etc.)
- [ ] NAP (Name, Address, Phone) present in the schema and consistent across the site
- [ ] Opening hours via `openingHours` or `openingHoursSpecification`
- [ ] Service area defined with `areaServed` or `serviceArea`
- [ ] AggregateRating or Review schema for star ratings in search results

## Maps and Directions

- [ ] Google Maps embed on the contact or homepage
- [ ] "Get Directions" link to Google Maps or Apple Maps
- [ ] Google Business Profile link (g.page or Google Maps place URL)

## Contact and Conversion

- [ ] Click-to-call `tel:` link for mobile users
- [ ] WhatsApp contact link (`wa.me` or `api.whatsapp.com`)
- [ ] Prominent call-to-action buttons (e.g. "Call Now", "Get a Quote", "Book Online")
- [ ] Contact form easily accessible

## Trust Signals

- [ ] Third-party review badges (Trustpilot, Checkatrade, Trustatrader, Feefo, reviews.io)
- [ ] Accreditation or certification logos
- [ ] Google reviews link or widget
- [ ] Trading Standards or industry body membership

## On-Page Essentials

- [ ] Business name in the page title and H1
- [ ] Location keywords in title, meta description, and headings
- [ ] Consistent NAP across header, footer, and contact page
- [ ] Local phone number (not just a national or 0800 number)
- [ ] Address visible in the footer or a dedicated contact section

## Google Business Profile

- [ ] GBP listing claimed and verified
- [ ] Categories set correctly (primary + secondary)
- [ ] Photos uploaded and up to date
- [ ] Posts and updates published regularly
- [ ] Q&A section monitored
- [ ] Link from website to GBP and from GBP back to website

## Citations and Directories

- [ ] Listed on major UK directories (Yell, Thomson Local, Yelp, FreeIndex)
- [ ] NAP consistent across all directory listings
- [ ] Industry-specific directories where relevant (e.g. Checkatrade, Bark, Houzz)

## Reviews

- [ ] Strategy for requesting reviews from customers
- [ ] Reviews schema markup on the website
- [ ] Links or badges pointing to review platforms
- [ ] Responding to reviews (both positive and negative)

## Technical

- [ ] Mobile-friendly design (most local searches are on mobile)
- [ ] Fast page load times (target under 3 seconds)
- [ ] HTTPS enabled
- [ ] Proper hreflang if serving multiple regions
- [ ] Local business schema validates in Google Rich Results Test

## Content

- [ ] Service pages for each main offering
- [ ] Location pages if serving multiple areas
- [ ] Blog or news section with locally relevant content
- [ ] Case studies or testimonials from local customers
- [ ] FAQ page addressing common local queries

## Scoring Weights (used by the Local SEO module)

| Signal                  | Points |
|-------------------------|--------|
| LocalBusiness schema    | 20     |
| NAP in schema           | 15     |
| Google Maps embed       | 10     |
| Click-to-call link      | 10     |
| Prominent CTA           | 10     |
| Opening hours           | 8      |
| Service area            | 7      |
| Review schema           | 5      |
| Trust signals           | 5      |
| GBP link                | 5      |
| WhatsApp link           | 3      |
| Directions link         | 2      |
| **Total**               | **100**|
