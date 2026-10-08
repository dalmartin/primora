"""One-time generator for company_labels.csv (Tauros's first pass, 2026-10-08).

After this runs once, company_labels.csv is the source of truth: edit the CSV, not this file.
Kept so the reasoning behind the first pass is visible.

Tier (PRD FR-4; Daniel 2026-09-23): prestige = FAANG+ and peers students rank alongside them
(top quant, top AI labs, elite unicorns); pipeline = a known feeder into prestige (Capital One
is Daniel's example): big established new-grad / intern programs at large tech, banks and
second-tier trading firms. Everything else: none.
"""
import csv
from pathlib import Path

GROUPS = {
    "big_tech": """Google; Meta; Apple; Amazon; Microsoft; Netflix; NVIDIA; LinkedIn; TikTok; ByteDance;
        Tencent; Samsung; Samsung Research America; Sony; Oracle; IBM; Salesforce; Adobe; Uber; Lyft;
        Airbnb; DoorDash; Pinterest; Snap Inc.; X Development; Intuit; Cisco; Dell Technologies; HP;
        Hewlett Packard Enterprise; eBay; Expedia; Yahoo; Reddit; Discord; Twitch; Zoom; Dropbox; Box;
        Spotify; Block; Square; Etsy; Wayfair; Roku; Amazon Robotics; Uber Freight; DiDi Global""",
    "quant": """Jane Street; Citadel; Citadel Securities; Hudson River Trading; Two Sigma; D. E. Shaw;
        Jump Trading; Optiver; IMC Trading; Susquehanna; Five Rings; Tower Research Capital; DRW;
        Akuna Capital; PEAK6; Chicago Trading Company; Belvedere Trading; Virtu; Old Mission;
        XTX Markets; G-Research; Point72; Schonfeld; Arrowstreet Capital; AQR Capital Management;
        PDT Partners; The Voleon Group; Hyannis Port Research; Geneva Trading; DV Trading;
        Garda Capital Partners; Maven Securities; Gelber Group; Walleye Capital; Quantbot Technologies;
        HBK Capital Management; Capstone Investment Advisors; Squarepoint Capital; Talos Trading;
        Stevens Capital Management; InfiniteQuant; Quantiq Partners; Aquatic Capital Management;
        Bracebridge Capital; Farallon Capital Management; Castleton Commodities International;
        Exegy; Databento; QuantCo; Blockhouse; Voloridge Health""",
    "finance": """Capital One; JPMorgan Chase; Bank of America; Citigroup; Wells Fargo; Goldman Sachs;
        Morgan Stanley; Barclays; BNY; State Street; Northern Trust; American Express; Visa; Mastercard;
        Discover; Synchrony; Ally Financial; US Bank; Fifth Third Bank; Citizens Financial Group;
        TD Bank; TD Securities; Royal Bank of Canada; Bank of Montreal; CIBC; Santander; ING; Webster Bank;
        Zions Bank; Axos Bank; Live Oak Bank; First National Bank; Fidelity Investments; Fidelity;
        Vanguard; Charles Schwab; T. Rowe Price; BlackRock; Blackstone; PIMCO; AllianceBernstein;
        Acadian Asset Management; Dimensional Fund Advisors; Artisan Partners; American Century Investments;
        MFS; Hamilton Lane; GCM Grosvenor; Cambridge Associates; William Blair; Baird; Lazard; Stifel;
        Nasdaq; CME Group; Cboe; Intercontinental Exchange; Tradeweb; MarketAxess; IEX Group; OCC;
        Options Clearing Corporation; Finra; S&P Global; Bloomberg; FactSet; Moody's; Thomson Reuters;
        Broadridge; SS&C; Arcesium; Clearwater Analytics; Enfusion; Addepar; Envestnet; AssetMark;
        Freddie Mac; Fannie Mae; Sallie Mae; Navy Federal; USAA; BECU; CoBank; Geico; State Farm;
        Allstate Insurance Company; Liberty Mutual Insurance; The Hartford; Progressive; Travelers;
        Northwestern Mutual; Prudential; MetLife; Pacific Life; Penn Mutual; Guardian Life; Thrivent;
        Principal Financial Group; Manulife; Sun Life; Empower; Voya Financial; Genworth; Athene;
        W.R. Berkley; Berkley Insurance; Arch Capital Group; Assurant; CNA Insurance; FM Global;
        Sentry; Sentry Insurance; Great American Insurance Company; American Financial Group;
        Western & Southern; Auto-Owners Insurance; COUNTRY Financial; Horace Mann; TruStage;
        National Indemnity; Equifax; Experian; Global Payments; Fiserv; FIS; Fidelity National Information Services;
        Western Union; Corpay; Wex; Computershare; LPL Financial Holdings; Rocket Mortgage;
        Rocket Companies; Credit Acceptance Careers; Primerica; Radian; MGIC; Chatham Financial;
        First American; Interactive Brokers; NinjaTrader; Apex Fintech Solutions; Federal Reserve Bank of Boston;
        Federal Reserve Bank of Chicago; The Federal Reserve System; Federal Reserve""",
    "fintech": """Stripe; Ramp; Robinhood; Coinbase; Plaid; Brex; Chime; SoFi; Affirm; PayPal; Toast;
        Mercury; Modern Treasury; Gemini; Ripple; Circle; Anchorage; Binance; Kraken; Remitly; Wealthsimple;
        Monzo; Acorns; Betterment; Perpay; MoneyLion; EarnIn; OnePay; Best Egg; Enova; Lendbuzz; nCino;
        BILL; Billtrust; Parafin; Galileo Financial Technologies; Dwolla; Lightspark; Altruist;
        Wealth.com; Zip; Persona; Early Warning; Interac; Tegus; Kensho; PitchBook; Ethic""",
    "ai": """OpenAI; Anthropic; xAI; Scale AI; Cohere; Together AI; Cerebras; Groq; SambaNova Systems;
        Etched; Perplexity; Glean; Mercor; Harvey; Abridge; Snorkel AI; Anyscale; Baseten; Suno;
        HeyGen; Hebbia; Codeium; Cursor; Replit; Typeface; Inworld; Sierra; Cresta; Kumo; Tenstorrent;
        d-Matrix; Crusoe; TensorWave; Lila Sciences; Mechanize; GenBio AI; Genesis Molecular AI;
        C3.ai; Domino Data Lab; DataRobot; SandboxAQ; Quantinuum; Rigetti; Field AI; Physical Intelligence""",
    "software": """Databricks; Snowflake; Palantir; Datadog; Cloudflare; MongoDB; Confluent; Atlassian;
        ServiceNow; Workday; Figma; Notion; Rippling; Gusto; Asana; Airtable; Vercel; Retool;
        HashiCorp; GitHub; GitLab; Twilio; Okta; CrowdStrike; Palo Alto Networks; Zscaler; Fortinet;
        SentinelOne; Tanium; Semgrep; Snyk; 1Password; Proofpoint; Rubrik; Cohesity; Nutanix;
        Pure Storage; NetApp; VMware; Red Hat; SAP; Autodesk; PTC; Cadence Design Systems; Synopsys;
        Ansys; athenahealth; Veeva; Samsara; Verkada; Klaviyo; HubSpot; Braze; Amplitude; Mixpanel;
        Sigma Computing; SingleStore; Starburst; Fivetran; dbt Labs; Cockroach Labs; YugaByte; Temporal;
        LaunchDarkly; Sentry; Fastly; Akamai Technologies; DigitalOcean; Equinix; Splunk; Elastic;
        Dynatrace; New Relic; PagerDuty; Docusign; Dropbox; Box; Zendesk; Qualtrics; Medallia; Workiva;
        Appian; UiPath; Pegasystems; Guidewire; Tyler Technologies; Blue Yonder; Manhattan Associates;
        Epicor; Infor; Kinaxis; Intapp; iManage; Seismic; Highspot; Gong; Outreach; Ironclad; AuditBoard;
        Rippling; Deel; Benchling; Tempus; Flatiron Health; Duolingo; Khan Academy; Grammarly; Canva;
        Squarespace; GoDaddy; Wix; Webflow; Unity; Roblox; Epic Games; Riot Games; Electronic Arts;
        Activision-Blizzard; Blizzard Entertainment; Zynga; Take-Two; Second Dinner; Scopely; Kabam;
        The Trade Desk; AppLovin; Moloco; Magnite; DoubleVerify; Integral Ad Science; LiveRamp; Taboola;
        ZipRecruiter; Handshake; Glassdoor; Indeed; Yelp; Nextdoor; Patreon; Strava; AllTrails; Bumble;
        Match Group; SeatGeek; StockX; WhatNot; Poshmark; ThredUp; Chewy; Instacart; Hudl; Klaviyo;
        Alarm.com; ZoomInfo; Five9; Dialpad; RingCentral; Bandwidth; Calix; Ciena; Juniper Networks;
        Arista Networks; Extreme Networks; F5; Viavi Solutions; Gen; Imprivata; SailPoint; Saviynt;
        KnowBe4; Recorded Future; Censys; Vectra; Illumio; Obsidian Security; Exiger; Esri; Trimble;
        Bentley Systems; Altair; Hexagon; AVEVA; AspenTech; Minitab; SAS; Tableau; Domo; Qlik;
        Kitware; MathWorks; Wolfram; Mozilla; Wikimedia Foundation; Atomic Object; WillowTree""",
    "hardware_semis": """Intel; AMD; Qualcomm; Broadcom; Marvell; Micron Technology; Texas Instruments;
        Analog Devices; KLA; Applied Materials; Lam Research; ASML; Tokyo Electron; TEL; GlobalFoundries;
        Western Digital; Seagate; Sandisk; Solidigm; Microchip Technology; NXP Semiconductors;
        Lattice Semiconductor; Silicon Labs; Skyworks; Qorvo; Cirrus Logic; Ambarella; Monolithic Power Systems;
        Semtech; Astera; Achronix Semiconductor; Rivos; SiMa.ai; Quadric; Graphcore; Arm Limited;
        Altera Corporation; Keysight; Teradyne; Onto Innovation; Axcelis; MKS Instruments; Lumentum;
        Coherent; Cognex; Zebra; Garmin; Logitech; Sonos; Bose; Shure; HARMAN; Arlo; Apple;
        Jabil; Flex; Plexus; TTM Technologies; Sensata; Corning; Western Digital; Pure Storage""",
    "defense_aerospace": """Lockheed Martin; RTX; Northrop Grumman; General Dynamics; General Dynamics Mission Systems;
        General Dynamics Information Technology; General Dynamics UK; Boeing; The Boeing Company; L3Harris Technologies;
        BAE Systems; Leidos; CACI; Booz Allen; SAIC; Peraton; ManTech; KBR; Parsons; Amentum; ICF;
        MITRE; The Aerospace Corporation; Johns Hopkins Applied Physics Laboratory; Draper; HRL Laboratories;
        SRI; Sierra Nevada Corporation; Sierra Space; Anduril; Shield AI; Saronic; Palantir; Skydio;
        SpaceX; Blue Origin; Rocket Lab; Relativity Space; Stoke Space; Firefly; Astranis; Planet;
        Capella Space; BlackSky; Maxar Technologies; Ball Aerospace; Axiom Space; Varda Space; Impulse Space;
        K2 Space; True Anomaly; Hermeus; Boom Supersonic; Joby Aviation; Archer; Wisk; Reliable Robotics;
        Merlin Labs; Skyryse; Ursa Major; Hadrian; CesiumAstro; AeroVironment; Teledyne; Moog;
        Curtiss-Wright Corporation; Mercury; Textron; Gulfstream; GE Aerospace; Collins Aerospace;
        Honeywell; Airbus; Thales; Thales Defense & Security, Inc.; Saab; Leonardo; Rolls Royce;
        United Launch Alliance; Iridium; Viasat; Intelsat; Echostar; Muon Space; Turion Space;
        Voyager Technologies; Apex; Innovative Defense Technologies; Two Six Technologies; Black Cape;
        Expedition Technology; Charles River Analytics; Radiance Technologies; Torch Technologies;
        Space Dynamics Laboratory; Advanced Space; Cubic; Smiths Detection; Echodyne; Silvus Technologies;
        Mach Industries; Nominal; Ultra; Ultra Intelligence and Communications; Akima; Nightwing Intelligence Solutions;
        GDIT; SMX; Calspan; Acron Aviation; Standard Aero; Panasonic Avionics; Aechelon Technology""",
    "auto_mobility": """Tesla; Waymo; Zoox; Cruise; Nuro; Aurora Innovation; Aurora; Rivian; Lucid; General Motors;
        GM financial; Ford; Toyota Research Institute; Woven; Mercedes-Benz; Nissan; Hyundai AutoEver America;
        XPeng Motors; WeRide; pony.ai; PlusAI; Plus; Kodiak; Bot Auto; Latitude AI; Applied Intuition;
        Motional; Zipline; Wing; Glydways; Parallel Systems; Harbinger Motors; Daimler Truck; Paccar;
        Oshkosh; Caterpillar Inc.; John Deere; CNH Industrial; Komatsu; BorgWarner; Aptiv; Magna;
        Bosch; Valeo; Zipcar; Revel; ChargePoint; Boston Dynamics; Boston Dynamics AI Institute;
        Apptronik; Figure; Symbotic; Locus Robotics; Simbe Robotics; Dusty Robotics; Gecko Robotics;
        Collaborative Robotics; Diligent Robotics; Bedrock Robotics; Carbon Robotics; Amp Robotics;
        Machina Labs; Intrinsic; Persona AI; Brain Corp; Multiply Labs; Picknik; Viam; Neuralink;
        The Boring Company; Lyft""",
    "health": """Epic; Medtronic; Intuitive Surgical; Stryker; Boston Scientific; Johnson & Johnson;
        Abbott; Becton Dickinson; Baxter International; Philips; Siemens Healthineers; GE Healthcare;
        Resmed; Dexcom; Insulet Corporation; Edwards Lifesciences; Hologic; Varian; Elekta; Zoll Medical;
        Smith+Nephew; Alcon; Globus Medical; LivaNova; Thermo Fisher Scientific; Illumina; Agilent Technologies;
        Bio-Rad Laboratories; Danaher Corporation; Cytiva; Waters Corporation; Revvity; Sartorius;
        Roche; Genentech; Pfizer; Moderna; Amgen; Gilead Sciences; AbbVie; Bristol Myers Squibb;
        Merck; MSD; Takeda; AstraZeneca; Daiichi Sankyo; Vertex Pharmaceuticals; Regeneron; Recursion Pharmaceuticals;
        Exact Sciences; GRAIL; Natera; Tempus; Element Biosciences; LabCorp; Quest Diagnostics;
        CVS Health; CVS Pharmacy; McKesson; Cardinal Health; Cencora; AmerisourceBergen; Medline;
        Henry Schein; UnitedHealth Group; Optum; Elevance Health; Cigna; Centene; Humana; Kaiser Permanente;
        Highmark Health; HCSC; Blue Cross Blue Shield; Premera Blue Cross; Blue Shield of California;
        Delta Dental; VSP Vision; Oscar Health; Garner Health; Nuna; Commure; Abridge; Zocdoc; Transcarent;
        Fresenius Medical Care; Fresenius Kabi; Modernizing Medicine; WellSky; Netsmart; Veeva; IDEXX;
        Zoetis; Resmed; Noah Medical; HeartFlow; PROCEPT BioRobotics; Imperative Care; Stanford Health Care;
        St. Jude Children's Research Hospital""",
    "consumer_media": """Walmart; Target; Costco; The Home Depot; Lowes; Best Buy; Nike; Lululemon; Nordstrom;
        Dick's Sporting Goods; Chick-fil-A; Starbucks; McDonald's; PepsiCo; Coca-Cola; P&G - Procter & Gamble;
        Nestle; Conagra Brands; Kraft Heinz; General Mills; Mars; Cargill; Sysco; US Foods; H-E-B; Kroger;
        Albertsons; 7-Eleven; Staples; Ace Hardware; Bass Pro Shops; L.L.Bean; Skechers; Columbia Sportswear Company;
        Arc'teryx Equipment; Alo Yoga; SharkNinja; Uline; Grainger; W.W. Grainger; The Walt Disney Company;
        Warner Bros. Discovery; Warner Bros.; NBCUniversal; Paramount; Comcast; Xfinity; Spectrum; Cox;
        Cox Enterprises; Dish; SiriusXM; iHeartMedia; Live Nation Entertainment; Ticketmaster; Sony Interactive Entertainment;
        PlayStation; Nintendo; The New York Times; The Washington Post; Washpost; Dow Jones; Hearst;
        DotDash Meredith; Scholastic; Pearson; HMH; MLB; Oklahoma City Thunder; Detroit Pistons; DraftKings;
        FanDuel; PrizePicks; Peloton; MyFitnessPal; Life Fitness; Chamberlain Group; Brunswick; Polaris;
        The Toro Company; Hyatt; Marriott; Choice Hotels; U-Haul; Enterprise; Southwest Airlines;
        United Airlines; Delta Air Lines; American Airlines; Breeze Airways; Sabre; ATPCO; Amadeus""",
    "industrial_energy": """GE Vernova; Siemens; Schneider Electric; ABB; Emerson Electric; Rockwell Automation;
        Johnson Controls; Honeywell; Carrier Global; Trane Technologies; Otis; Lennox; Eaton Corporation;
        Generac; Vertiv; nVent; Xylem; Itron; Badger Meter; Watts Water; Graco; Nordson; Illinois Tool Works;
        Dover; Fortive; Regal Rexnord; Stanley Black & Decker; Allegion; ASSA ABLOY; Terex; Vermeer;
        Wabtec; Westinghouse Electric Company; Bloom Energy; Plug Power; Kairos Power; Commonwealth Fusion Systems;
        Antora Energy; Base Power; Span; Electric Hydrogen; Nextracker; Energy Vault; Xcimer Energy;
        Chevron Corporation; Exxon Mobil; Marathon Petroleum; Baker Hughes; NOV; ChampionX; Vistra;
        NRG Energy; Ameren; Eversource Energy; NiSource; IGS Energy; Tesla Energy; Schweitzer Engineering Laboratories;
        SEL; EquipmentShare; C.H. Robinson; Echo Global Logistics; Ryder System; Dayton Freight Lines;
        United Parcel Service (UPS); FedEx; Flexport; Shamrock Trading; Spot Freight; Steel Dynamics;
        Carpenter Technology; Corteva Agriscience; Corteva; Kimley-Horn; Jacobs; WSP; HNTB; Sargent & Lundy;
        Burns & McDonnell; Black & Veatch; Hypertherm Associates; Formlabs; Xometry; Lumafield; Markforged;
        Marmon Holdings; Valmont; Leggett & Platt; Masco; Pella Corporation; Daifuku; Autostore;
        Vanderlande Industries; KION Group; Kodak; Canon; Toshiba Global Commerce; Brady""",
    "telecom": """Verizon; T-Mobile; AT&T; Comcast; Charter; Lumen; CenturyLink; Nokia; Ericsson; Motorola Solutions;
        CommScope; Iridium; Gogo; Boingo; TDS; TELUS Digital""",
    "consulting_services": """Deloitte; PwC; PricewaterhouseCoopers (PwC); KPMG; EY; Accenture; McKinsey; BCG; Bain;
        ZS; RSM; Booz Allen; CGI; Kyndryl Holdings; Unisys; Avanade; Slalom; Capgemini; Infosys; TCS;
        Persistent Systems; Robert Half; EisnerAmper; Marsh; Gartner; Specialisterne; ALKU; Konrad;
        Lean TECHniques; Jahnel Group; Viget""",
    "gov_research": """National Renewable Energy Laboratory; Fermilab; Savannah River National Laboratory;
        Lawrence Livermore National Laboratory; Los Alamos National Laboratory; Sandia National Laboratories;
        Oak Ridge National Laboratory; Argonne National Laboratory; Pacific Northwest National Laboratory;
        NASA; Carnegie Mellon University; Washington University in St. Louis; Emory University;
        WGU - Western Governors University; WGU; Dordt University; Simons Foundation; Arkansas Center for Data Sciences;
        Oklahoma State Government; Commonwealth of Massachusetts; State of Wisconsin Investment Board;
        USAFacts; Southern Poverty Law Center; Compassion International; ALSAC; Ithaka; OCLC;
        Art of Problem Solving; Mission Bit""",
}

PRESTIGE = """Google; Meta; Apple; Amazon; Microsoft; Netflix; NVIDIA; OpenAI; Anthropic; xAI; Stripe;
    Databricks; Palantir; Jane Street; Citadel; Citadel Securities; Hudson River Trading; Two Sigma; D. E. Shaw;
    Jump Trading; Optiver; IMC Trading; Susquehanna; Five Rings; Tower Research Capital; DRW; PDT Partners;
    XTX Markets; G-Research; Point72; Ramp; Scale AI; Figma; Notion; Roblox; Airbnb; Uber; LinkedIn;
    Snowflake; Coinbase; Robinhood; Pinterest; Snap Inc.; DoorDash; Waymo; SpaceX; Anduril; Bloomberg;
    TikTok; ByteDance; Tesla; Plaid; Rippling; Cloudflare; Datadog; Lyft; Applied Intuition; Neuralink;
    Zoox; Glean; Cohere; Perplexity; Cursor; Replit; Vercel; Discord; Reddit; Instacart; Spotify;
    Salesforce; Adobe; Duolingo; Brex; Mercury; Cerebras; Groq; Etched; Together AI; Anyscale; Harvey;
    Abridge; Mercor; Shield AI; Saronic; Skydio; Zipline; Benchling; Epic Games; Riot Games;
    The Voleon Group; Old Mission; X Development; Hebbia; Physical Intelligence""".split(";")

PIPELINE = """Capital One; JPMorgan Chase; Bank of America; Citigroup; Wells Fargo; Goldman Sachs; Morgan Stanley;
    American Express; Visa; Mastercard; PayPal; Discover; Fidelity Investments; Vanguard; Charles Schwab;
    BlackRock; BNY; State Street; Barclays; T. Rowe Price; Geico; USAA; Intuit; IBM; Oracle; Cisco;
    Qualcomm; AMD; Intel; Dell Technologies; HP; Hewlett Packard Enterprise; ServiceNow; Workday; Atlassian;
    Autodesk; Cadence Design Systems; Synopsys; Red Hat; VMware; Walmart; Target; eBay; Expedia; Wayfair;
    Chewy; Electronic Arts; Activision-Blizzard; Blizzard Entertainment; The Walt Disney Company;
    T-Mobile; Verizon; Comcast; Akuna Capital; PEAK6; Chicago Trading Company; Belvedere Trading; Virtu;
    Arrowstreet Capital; AQR Capital Management; Schonfeld; Hyannis Port Research; DV Trading; Geneva Trading;
    Gelber Group; Squarepoint Capital; Garda Capital Partners; Talos Trading; Nasdaq; CME Group; Cboe;
    Tradeweb; S&P Global; Lockheed Martin; RTX; Northrop Grumman; Boeing; The Boeing Company;
    General Dynamics Mission Systems; L3Harris Technologies; MongoDB; Confluent; Twilio; Okta; CrowdStrike;
    Palo Alto Networks; Zscaler; Dropbox; Box; Docusign; Samsara; Verkada; Affirm; SoFi; Chime; Block;
    Square; Toast; Gusto; Asana; HubSpot; The Trade Desk; Roku; Sony Interactive Entertainment; Nintendo;
    Yelp; Zillow; Wealthfront; Klaviyo; Datadog; Micron Technology; Texas Instruments; KLA; Applied Materials;
    Marvell; Broadcom; Analog Devices; Western Digital; Rivian; Lucid; General Motors; Ford; John Deere;
    Caterpillar Inc.; Honeywell; Epic; Bloomberg; FactSet; Moody's; Thomson Reuters; Northern Trust;
    Liberty Mutual Insurance; State Farm; Allstate Insurance Company; Northwestern Mutual; Ally Financial;
    US Bank; TD Bank; Royal Bank of Canada; Bank of Montreal; CIBC; Synchrony; Citizens Financial Group;
    Fifth Third Bank; Accenture; Deloitte; Booz Allen; Leidos""".split(";")


def clean(names):
    return [n.strip() for n in names if n.strip()]


def main():
    rows = {}
    for group, names in GROUPS.items():
        for n in clean(names.split(";")):
            rows.setdefault(n, {"company_name": n, "tier": "none", "group": group})
    prestige, pipeline = set(clean(PRESTIGE)), set(clean(PIPELINE)) - set(clean(PRESTIGE))
    for n in prestige | pipeline:
        rows.setdefault(n, {"company_name": n, "tier": "none", "group": "other"})
        rows[n]["tier"] = "prestige" if n in prestige else "pipeline"
    out = Path(__file__).with_name("company_labels.csv")
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["company_name", "tier", "group"])
        w.writeheader()
        w.writerows(sorted(rows.values(), key=lambda r: (r["group"], r["company_name"].lower())))
    print(f"{len(rows)} labels -> {out}")


if __name__ == "__main__":
    main()
