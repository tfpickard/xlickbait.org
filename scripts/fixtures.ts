/**
 * Development fixtures.
 *
 * Every arXiv id here is deliberately impossible -- `0000.NNNNN` is not a shape
 * arXiv has ever issued -- so a fixture can never be mistaken for a real paper or
 * point a visitor at someone's actual work. Titles, abstracts and authors are
 * invented.
 *
 * The `anchor` of every fixture headline appears verbatim in that paper's title
 * or abstract. Phase 2 enforces that with a hard truth gate; holding the fixtures
 * to the same standard keeps them an honest example of the contract rather than a
 * special case that would not survive it.
 *
 * The spread of `publish_at` is load-bearing for the tests:
 *   - most rows are in the past and visible
 *   - two are in the FUTURE and must stay invisible until their time comes
 *   - one is `hidden` and must never appear at all
 *   - two share an identical `publish_at`, which is what makes the cursor
 *     tiebreaker testable rather than theoretical
 */

export interface PaperFixture {
	arxivId: string;
	title: string;
	abstract: string;
	authors: string[];
	primaryCategory: string;
	categories: string[];
	publishedAt: string;
	absUrl: string;
}

export interface HeadlineFixture {
	arxivId: string;
	headline: string;
	dek: string;
	anchor: string;
	actualPoint: string;
	kind: 'fresh' | 'vintage';
	model: string;
	status: 'published' | 'hidden';
	publishAt: string;
}

const HOUR = 3600 * 1000;
const DAY = 24 * HOUR;

/** Fixed base so seeded data is reproducible relative to seed time. */
function at(offsetMs: number): string {
	return new Date(Date.now() + offsetMs).toISOString();
}

export const paperFixtures: PaperFixture[] = [
	{
		arxivId: '0000.00001',
		title: 'A Refined Upper Bound on Neutrino Mass from Three Years of Cryogenic Calorimetry',
		abstract:
			'We report a refined upper bound on the effective electron antineutrino mass using three years of data from a bolometer array operated at 10 mK. The detector was calibrated fortnightly. Systematic uncertainties are dominated by the energy scale reconstruction.',
		authors: ['R. Alvarez', 'M. Okonkwo', 'S. Lindqvist'],
		primaryCategory: 'hep-ex',
		categories: ['hep-ex', 'physics.ins-det'],
		publishedAt: at(-3 * DAY),
		absUrl: 'https://arxiv.org/abs/0000.00001'
	},
	{
		arxivId: '0000.00002',
		title: 'Near-Linear Time Graph Partitioning with Provable Conductance Guarantees',
		abstract:
			'We present a near-linear time algorithm for balanced graph partitioning. We evaluate on standard benchmarks including the road network of Luxembourg, where our method reduces edge cut by 11% over the previous best.',
		authors: ['J. Whitfield', 'P. Ramanathan'],
		primaryCategory: 'cs.DS',
		categories: ['cs.DS', 'cs.DM'],
		publishedAt: at(-2 * DAY),
		absUrl: 'https://arxiv.org/abs/0000.00002'
	},
	{
		arxivId: '0000.00003',
		title: 'Atmospheric Retrieval for a Warm Neptune with JWST Transit Spectroscopy',
		abstract:
			'We analyse 47 hours of telescope time targeting a warm Neptune. The retrieved spectrum is consistent with a cloudy atmosphere. Water abundance is constrained to within a factor of three.',
		authors: ['H. Nakamura', 'F. Dubois', 'L. Achterberg', 'T. Mensah'],
		primaryCategory: 'astro-ph.EP',
		categories: ['astro-ph.EP', 'astro-ph.IM'],
		publishedAt: at(-4 * DAY),
		absUrl: 'https://arxiv.org/abs/0000.00003'
	},
	{
		arxivId: '0000.00004',
		title: 'Sample-Efficient Offline Reinforcement Learning under Distribution Shift',
		abstract:
			'We propose a conservative value estimator for offline reinforcement learning. Experiments use a replay buffer of 2.3 million transitions collected from a simulated forklift. Performance degrades gracefully in some regimes.',
		authors: ['A. Petrova', 'D. Kim'],
		primaryCategory: 'cs.LG',
		categories: ['cs.LG', 'cs.AI', 'stat.ML'],
		publishedAt: at(-1 * DAY),
		absUrl: 'https://arxiv.org/abs/0000.00004'
	},
	{
		arxivId: '0000.00005',
		title: 'On the Distribution of Gaps Between Consecutive Prime Powers',
		abstract:
			'We establish new bounds on the distribution of gaps between consecutive prime powers, improving on classical estimates. The proof proceeds by a sieve argument and requires no unproven hypotheses.',
		authors: ['V. Sørensen'],
		primaryCategory: 'math.NT',
		categories: ['math.NT'],
		publishedAt: at(-6 * DAY),
		absUrl: 'https://arxiv.org/abs/0000.00005'
	},
	{
		arxivId: '0000.00006',
		title: 'Thermal Tolerance in Antarctic Notothenioid Fish under Projected Warming',
		abstract:
			'We measured critical thermal maxima for six notothenioid species. Median tolerance was 13.2 degrees Celsius. Individuals were held in aquaria for 21 days prior to trials and fed a diet of commercial pellets.',
		authors: ['C. Bergström', 'N. Haruki'],
		primaryCategory: 'q-bio.PE',
		categories: ['q-bio.PE'],
		publishedAt: at(-5 * DAY),
		absUrl: 'https://arxiv.org/abs/0000.00006'
	},
	{
		arxivId: '0000.00007',
		title: 'A Distributed Consensus Protocol Tolerating Partial Synchrony',
		abstract:
			'We describe a consensus protocol that terminates under partial synchrony. The protocol was deployed across 400 nodes in a single datacentre in Ohio for a two-week evaluation period.',
		authors: ['M. El-Sayed', 'K. Novak'],
		primaryCategory: 'cs.DC',
		categories: ['cs.DC', 'cs.NI'],
		publishedAt: at(-8 * DAY),
		absUrl: 'https://arxiv.org/abs/0000.00007'
	},
	{
		arxivId: '0000.00008',
		title: 'Anomalous Viscosity in Granular Flows of Irregular Particles',
		abstract:
			'Granular flows of irregular particles exhibit anomalous effective viscosity. Our apparatus used 1.4 tonnes of crushed basalt. We observe a transition at a packing fraction of 0.61.',
		authors: ['G. Marchetti', 'Y. Oyelaran'],
		primaryCategory: 'cond-mat.soft',
		categories: ['cond-mat.soft', 'physics.geo-ph'],
		publishedAt: at(-9 * DAY),
		absUrl: 'https://arxiv.org/abs/0000.00008'
	},
	{
		arxivId: '0000.00009',
		title: 'Formal Verification of a Railway Interlocking System',
		abstract:
			'We formally verify a railway interlocking using a model checker. The specification comprises 11,000 lines and was checked against the timetable of a regional network in Belgium.',
		authors: ['I. Vandenberghe'],
		primaryCategory: 'cs.LO',
		categories: ['cs.LO', 'cs.SE'],
		publishedAt: at(-12 * DAY),
		absUrl: 'https://arxiv.org/abs/0000.00009'
	},
	{
		arxivId: '0000.00010',
		title: 'Magnetohydrodynamic Simulations of Accretion Disc Instabilities',
		abstract:
			'We run global magnetohydrodynamic simulations of accretion discs. Each run consumed approximately 900,000 CPU hours. The magnetorotational instability saturates earlier than previously reported.',
		authors: ['S. Bianchi', 'W. Adeyemi', 'Q. Zhao'],
		primaryCategory: 'astro-ph.HE',
		categories: ['astro-ph.HE', 'physics.plasm-ph'],
		publishedAt: at(-15 * DAY),
		absUrl: 'https://arxiv.org/abs/0000.00010'
	},
	{
		arxivId: '0000.00011',
		title: 'Compressed Sensing Recovery Guarantees for Structured Sparsity',
		abstract:
			'We derive recovery guarantees for compressed sensing under structured sparsity assumptions. A worked example uses a dictionary of 512 atoms.',
		authors: ['B. Iversen', 'R. Chakraborty'],
		primaryCategory: 'cs.IT',
		categories: ['cs.IT', 'math.IT'],
		publishedAt: at(-20 * DAY),
		absUrl: 'https://arxiv.org/abs/0000.00011'
	},
	{
		arxivId: '0000.00012',
		title: 'Soil Microbial Community Response to Long-Term Nitrogen Addition',
		abstract:
			'A 19-year nitrogen addition experiment altered soil microbial community composition. Plots were mown twice annually. Fungal to bacterial ratio declined monotonically.',
		authors: ['E. Lindgren', 'O. Mwangi'],
		primaryCategory: 'q-bio.PE',
		categories: ['q-bio.PE', 'physics.bio-ph'],
		publishedAt: at(-25 * DAY),
		absUrl: 'https://arxiv.org/abs/0000.00012'
	},
	{
		arxivId: '0000.00013',
		title: 'A Type System for Effect Polymorphism in a Call-by-Push-Value Calculus',
		abstract:
			'We present a type system for effect polymorphism. Soundness is proved by a logical relations argument spanning 60 pages of appendix.',
		authors: ['T. Lindholm'],
		primaryCategory: 'cs.PL',
		categories: ['cs.PL', 'cs.LO'],
		publishedAt: at(-30 * DAY),
		absUrl: 'https://arxiv.org/abs/0000.00013'
	},
	{
		arxivId: '0000.00014',
		title: 'Seismic Attenuation Beneath the Central Andes from Teleseismic Data',
		abstract:
			'We image seismic attenuation beneath the Central Andes. Stations were serviced by mule. The resulting model shows a low-Q anomaly at 80 km depth.',
		authors: ['P. Quispe', 'A. Restrepo'],
		primaryCategory: 'physics.geo-ph',
		categories: ['physics.geo-ph'],
		publishedAt: at(-40 * DAY),
		absUrl: 'https://arxiv.org/abs/0000.00014'
	}
];

export const headlineFixtures: HeadlineFixture[] = [
	{
		arxivId: '0000.00001',
		headline:
			'Physicists Built A Room Colder Than Deep Space. What They Did In There Is Technically Legal.',
		dek: 'They will not say what happens at 10 mK. The paper simply moves on.',
		anchor: 'a bolometer array operated at 10 mK',
		actualPoint:
			'The paper reports a refined upper bound on neutrino mass from three years of detector data.',
		kind: 'fresh',
		model: 'fixture',
		status: 'published',
		publishAt: at(-2 * HOUR)
	},
	{
		arxivId: '0000.00002',
		headline: "Why Are Computer Scientists So Obsessed With Luxembourg's Roads?",
		dek: 'A nation of 650,000 people keeps turning up in algorithm papers. Experts have not explained it.',
		anchor: 'the road network of Luxembourg',
		actualPoint:
			'It is a near-linear time graph partitioning algorithm with conductance guarantees.',
		kind: 'fresh',
		model: 'fixture',
		status: 'published',
		publishAt: at(-5 * HOUR)
	},
	{
		arxivId: '0000.00003',
		headline:
			'Astronomers Spent 47 HOURS Staring At One Planet. You Won’t Believe What They Found (Clouds)',
		dek: 'Two full days of the most expensive telescope ever built, and the answer was weather.',
		anchor: '47 hours of telescope time',
		actualPoint: 'It is an atmospheric retrieval constraining water abundance on a warm Neptune.',
		kind: 'fresh',
		model: 'fixture',
		status: 'published',
		publishAt: at(-9 * HOUR)
	},
	{
		arxivId: '0000.00004',
		headline:
			'Scientists Trained An AI On 2.3 Million Forklift Decisions. It Works In SOME Regimes.',
		dek: 'Researchers decline to specify which regimes. The forklift was simulated, they insist.',
		anchor: 'a simulated forklift',
		actualPoint: 'It proposes a conservative value estimator for offline reinforcement learning.',
		kind: 'fresh',
		model: 'fixture',
		status: 'published',
		publishAt: at(-14 * HOUR)
	},
	{
		arxivId: '0000.00005',
		headline:
			'This One Weird Sieve Argument Requires NO Unproven Hypotheses. Mathematicians Baffled.',
		dek: 'An entire field built on assumptions, and one paper just declined to make any.',
		anchor: 'requires no unproven hypotheses',
		actualPoint: 'It establishes new bounds on gaps between consecutive prime powers.',
		kind: 'fresh',
		model: 'fixture',
		status: 'published',
		publishAt: at(-22 * HOUR)
	},
	{
		arxivId: '0000.00006',
		headline: 'Antarctic Fish Were Held In Tanks For 21 Days And Fed COMMERCIAL PELLETS',
		dek: 'The pellets are described only as commercial. No brand is named anywhere in the paper.',
		anchor: 'fed a diet of commercial pellets',
		actualPoint: 'It measures critical thermal maxima for six notothenioid species under warming.',
		kind: 'fresh',
		model: 'fixture',
		status: 'published',
		publishAt: at(-30 * HOUR)
	},
	{
		arxivId: '0000.00007',
		headline: 'There Are 400 Machines In An Ohio Basement Agreeing With Each Other. For Two Weeks.',
		dek: 'What were they agreeing about? The paper calls it consensus and leaves it there.',
		anchor: '400 nodes in a single datacentre in Ohio',
		actualPoint: 'It describes a consensus protocol that terminates under partial synchrony.',
		kind: 'vintage',
		model: 'fixture',
		status: 'published',
		publishAt: at(-2 * DAY)
	},
	{
		arxivId: '0000.00008',
		headline: 'Someone Ordered 1.4 TONNES Of Crushed Basalt And Science Was The Excuse',
		dek: 'The rock was poured, repeatedly, until something happened at 0.61.',
		anchor: '1.4 tonnes of crushed basalt',
		actualPoint:
			'It characterises anomalous effective viscosity in granular flows of irregular particles.',
		kind: 'vintage',
		model: 'fixture',
		status: 'published',
		publishAt: at(-3 * DAY)
	},
	{
		arxivId: '0000.00009',
		headline: 'The Belgian Train Timetable Has Been Mathematically PROVEN. Commuters Unmoved.',
		dek: 'Eleven thousand lines of specification later, the trains run exactly as before.',
		anchor: 'the timetable of a regional network in Belgium',
		actualPoint: 'It formally verifies a railway interlocking system using a model checker.',
		kind: 'vintage',
		model: 'fixture',
		status: 'published',
		publishAt: at(-4 * DAY)
	},
	{
		arxivId: '0000.00010',
		headline: 'Astronomers Burned 900,000 CPU Hours. The Instability Saturated EARLY.',
		dek: 'Nearly a century of continuous computation, and it finished ahead of schedule.',
		anchor: 'approximately 900,000 CPU hours',
		actualPoint:
			'It runs global MHD simulations showing the magnetorotational instability saturates early.',
		kind: 'vintage',
		model: 'fixture',
		status: 'published',
		publishAt: at(-5 * DAY)
	},
	{
		arxivId: '0000.00011',
		headline: 'A Dictionary With Only 512 Words In It Is Somehow Enough. Linguists Not Consulted.',
		dek: 'The atoms are not letters. Researchers were unable to clarify further.',
		anchor: 'a dictionary of 512 atoms',
		actualPoint: 'It derives compressed sensing recovery guarantees under structured sparsity.',
		kind: 'vintage',
		model: 'fixture',
		status: 'published',
		publishAt: at(-6 * DAY)
	},
	{
		arxivId: '0000.00012',
		headline: 'Scientists Mowed The Same Field Twice A Year For 19 YEARS. Something Declined.',
		dek: 'Nearly two decades of mowing. The ratio went down monotonically and nobody stopped it.',
		anchor: 'Plots were mown twice annually',
		actualPoint: 'It reports soil microbial community response to long-term nitrogen addition.',
		kind: 'vintage',
		model: 'fixture',
		status: 'published',
		publishAt: at(-7 * DAY)
	},
	{
		arxivId: '0000.00013',
		headline: 'This Proof Has A 60-PAGE APPENDIX. Experts Say That Is Where They Keep It.',
		dek: 'Sixty pages nobody has read, sitting at the back of a paper about effects.',
		anchor: '60 pages of appendix',
		actualPoint:
			'It presents a type system for effect polymorphism, proved sound by logical relations.',
		kind: 'vintage',
		model: 'fixture',
		status: 'hidden',
		publishAt: at(-8 * DAY)
	},
	{
		arxivId: '0000.00014',
		headline: 'Seismic Stations In The Andes Are Serviced BY MULE. This Is Not A Metaphor.',
		dek: 'In an age of satellites, the data still comes down the mountain on an animal.',
		anchor: 'Stations were serviced by mule',
		actualPoint: 'It images seismic attenuation beneath the Central Andes from teleseismic data.',
		kind: 'fresh',
		model: 'fixture',
		status: 'published',
		publishAt: at(3 * HOUR)
	}
];

/**
 * A second future-dated paper, so "future rows stay hidden" is tested by more
 * than a single row.
 */
paperFixtures.push({
	arxivId: '0000.00015',
	title: 'Photonic Crystal Waveguides with Engineered Slow-Light Regions',
	abstract:
		'We fabricate photonic crystal waveguides with engineered slow-light regions. Devices were written by electron beam lithography over a period of 11 nights.',
	authors: ['K. Sundaram', 'L. Fiorentino'],
	primaryCategory: 'physics.optics',
	categories: ['physics.optics', 'cond-mat.mes-hall'],
	publishedAt: at(-11 * DAY),
	absUrl: 'https://arxiv.org/abs/0000.00015'
});

headlineFixtures.push({
	arxivId: '0000.00015',
	headline:
		'Scientists Worked 11 NIGHTS In A Row With An Electron Beam. Nobody Asked Why At Night.',
	dek: 'The lithography happens after dark. The paper offers no explanation for this.',
	anchor: 'over a period of 11 nights',
	actualPoint:
		'It reports fabrication of photonic crystal waveguides with engineered slow-light regions.',
	kind: 'fresh',
	model: 'fixture',
	status: 'published',
	publishAt: at(26 * HOUR)
});

/**
 * Force two PUBLISHED headlines on DIFFERENT papers to share an identical
 * `publish_at`.
 *
 * It has to be different papers: the partial unique index allows only one
 * published headline per paper, so a same-paper pair could never exist in
 * production and would be a fake test. Different papers with the same timestamp
 * is precisely what the generator produces every time it writes a batch, and it
 * is the case where a cursor keyed on `publish_at` alone silently duplicates or
 * skips a row at the page boundary.
 */
const TIE = at(-11 * HOUR);
export const TIED_ARXIV_IDS = ['0000.00010', '0000.00011'] as const;
for (const arxivId of TIED_ARXIV_IDS) {
	const fixture = headlineFixtures.find((h) => h.arxivId === arxivId && h.status === 'published');
	if (!fixture) throw new Error(`fixture invariant broken: no published headline for ${arxivId}`);
	fixture.publishAt = TIE;
}

/**
 * A larger back catalogue.
 *
 * Twelve live headlines is not enough to exercise anything: the front page alone
 * renders ten, which leaves no pool for the chumbox and no second page for the
 * cursor. These push the corpus past both thresholds so the tests measure real
 * behaviour instead of a degenerate case.
 */
const backCatalogue: [PaperFixture, Omit<HeadlineFixture, 'arxivId'>][] = [
	[
		{
			arxivId: '0000.00016',
			title: 'Turbulent Boundary Layer Measurements in a Low-Speed Wind Tunnel',
			abstract:
				'We report boundary layer measurements at Reynolds numbers up to 40,000. The tunnel was recalibrated after a pigeon entered the intake during preliminary testing.',
			authors: ['D. Ferreira', 'M. Aaltonen'],
			primaryCategory: 'physics.flu-dyn',
			categories: ['physics.flu-dyn'],
			publishedAt: at(-18 * DAY),
			absUrl: 'https://arxiv.org/abs/0000.00016'
		},
		{
			headline: 'A PIGEON Got Into The Experiment And Researchers Just Recalibrated And Moved On',
			dek: 'The bird is mentioned once, in passing, and then never again.',
			anchor: 'a pigeon entered the intake',
			actualPoint:
				'It reports turbulent boundary layer measurements at Reynolds numbers up to 40,000.',
			kind: 'vintage',
			model: 'fixture',
			status: 'published',
			publishAt: at(-32 * HOUR)
		}
	],
	[
		{
			arxivId: '0000.00017',
			title: 'Lattice QCD Determination of the Pion Decay Constant',
			abstract:
				'We determine the pion decay constant from lattice QCD. The calculation used 18 months of wall-clock time on a leadership-class facility and four independent lattice spacings.',
			authors: ['S. Haldar', 'E. Toivonen'],
			primaryCategory: 'hep-lat',
			categories: ['hep-lat', 'hep-ph'],
			publishedAt: at(-22 * DAY),
			absUrl: 'https://arxiv.org/abs/0000.00017'
		},
		{
			headline: 'Physicists Spent 18 MONTHS Computing One Number. Experts Say It Is A Constant.',
			dek: 'A year and a half of the fastest computers on Earth, for a quantity that does not change.',
			anchor: '18 months of wall-clock time',
			actualPoint:
				'It determines the pion decay constant from lattice QCD at four lattice spacings.',
			kind: 'vintage',
			model: 'fixture',
			status: 'published',
			publishAt: at(-38 * HOUR)
		}
	],
	[
		{
			arxivId: '0000.00018',
			title: 'Adaptive Mesh Refinement for Coastal Inundation Modelling',
			abstract:
				'We apply adaptive mesh refinement to coastal inundation. The model was validated against tide gauge records from a single pier in Cornwall spanning 1953 to 2019.',
			authors: ['R. Trelawny', 'A. Nwosu'],
			primaryCategory: 'physics.ao-ph',
			categories: ['physics.ao-ph', 'cs.CE'],
			publishedAt: at(-27 * DAY),
			absUrl: 'https://arxiv.org/abs/0000.00018'
		},
		{
			headline: 'One Pier In Cornwall Has Been Quietly Recording Everything Since 1953',
			dek: 'Sixty-six years of measurements from a single structure. Nobody has explained who authorised this.',
			anchor: 'a single pier in Cornwall spanning 1953 to 2019',
			actualPoint: 'It applies adaptive mesh refinement to coastal inundation modelling.',
			kind: 'vintage',
			model: 'fixture',
			status: 'published',
			publishAt: at(-45 * HOUR)
		}
	],
	[
		{
			arxivId: '0000.00019',
			title: 'Differential Privacy Guarantees for Federated Median Estimation',
			abstract:
				'We give differential privacy guarantees for federated median estimation. The privacy budget epsilon was fixed at 0.5 throughout. Utility degrades sharply below 100 participants.',
			authors: ['J. Okafor', 'L. Beaumont'],
			primaryCategory: 'cs.CR',
			categories: ['cs.CR', 'cs.LG'],
			publishedAt: at(-16 * DAY),
			absUrl: 'https://arxiv.org/abs/0000.00019'
		},
		{
			headline: 'Scientists Set Privacy To 0.5 And Refused To Elaborate Further',
			dek: 'Half of one epsilon. The paper treats this as self-explanatory.',
			anchor: 'The privacy budget epsilon was fixed at 0.5 throughout',
			actualPoint: 'It provides differential privacy guarantees for federated median estimation.',
			kind: 'fresh',
			model: 'fixture',
			status: 'published',
			publishAt: at(-52 * HOUR)
		}
	],
	[
		{
			arxivId: '0000.00020',
			title: 'Radiocarbon Chronology of a Neolithic Midden Deposit',
			abstract:
				'We present a radiocarbon chronology for a Neolithic midden. The deposit consists largely of oyster shells, of which 12,000 were counted individually.',
			authors: ['H. Lindqvist', 'P. Oduya'],
			primaryCategory: 'physics.geo-ph',
			categories: ['physics.geo-ph'],
			publishedAt: at(-35 * DAY),
			absUrl: 'https://arxiv.org/abs/0000.00020'
		},
		{
			headline: 'Somebody Counted 12,000 Oyster Shells By Hand. That Somebody Has A Doctorate.',
			dek: 'Twelve thousand. Individually. The paper does not say how long it took.',
			anchor: '12,000 were counted individually',
			actualPoint: 'It presents a radiocarbon chronology for a Neolithic midden deposit.',
			kind: 'vintage',
			model: 'fixture',
			status: 'published',
			publishAt: at(-60 * HOUR)
		}
	],
	[
		{
			arxivId: '0000.00021',
			title: 'A Lower Bound for Monotone Circuit Depth of Matching',
			abstract:
				'We prove a lower bound for monotone circuit depth of the matching function. The argument is elementary and fits on two pages.',
			authors: ['N. Krastev'],
			primaryCategory: 'cs.CC',
			categories: ['cs.CC', 'math.CO'],
			publishedAt: at(-44 * DAY),
			absUrl: 'https://arxiv.org/abs/0000.00021'
		},
		{
			headline: 'This Entire Proof Fits On TWO PAGES And Theorists Are Reportedly Furious',
			dek: 'Decades of effort, and the argument is described by its own author as elementary.',
			anchor: 'The argument is elementary and fits on two pages',
			actualPoint: 'It proves a lower bound for the monotone circuit depth of matching.',
			kind: 'vintage',
			model: 'fixture',
			status: 'published',
			publishAt: at(-70 * HOUR)
		}
	],
	[
		{
			arxivId: '0000.00022',
			title: 'Observation of Anomalous Hall Effect in a Kagome Metal',
			abstract:
				'We observe an anomalous Hall effect in a kagome metal. Samples were grown over six weeks and stored under argon in a converted refrigerator.',
			authors: ['Y. Matsuda', 'B. Okonjo'],
			primaryCategory: 'cond-mat.str-el',
			categories: ['cond-mat.str-el', 'cond-mat.mtrl-sci'],
			publishedAt: at(-13 * DAY),
			absUrl: 'https://arxiv.org/abs/0000.00022'
		},
		{
			headline: 'There Is A Converted Refrigerator In A Physics Lab And It Is Full Of Argon',
			dek: 'Six weeks of growth, stored in a repurposed appliance. The brand is not disclosed.',
			anchor: 'stored under argon in a converted refrigerator',
			actualPoint: 'It reports observation of the anomalous Hall effect in a kagome metal.',
			kind: 'fresh',
			model: 'fixture',
			status: 'published',
			publishAt: at(-76 * HOUR)
		}
	],
	[
		{
			arxivId: '0000.00023',
			title: 'Gradient Flow Dynamics in Wide Two-Layer Networks',
			abstract:
				'We analyse gradient flow in wide two-layer networks. Our analysis holds in the limit of infinite width, which no practitioner has ever trained.',
			authors: ['C. Avram', 'T. Ishikawa'],
			primaryCategory: 'stat.ML',
			categories: ['stat.ML', 'cs.LG', 'math.OC'],
			publishedAt: at(-10 * DAY),
			absUrl: 'https://arxiv.org/abs/0000.00023'
		},
		{
			headline: 'Researchers Admit Nobody Has Ever Trained The Thing They Analysed',
			dek: 'The limit is infinite. The practitioners are finite. The gap is acknowledged in writing.',
			anchor: 'which no practitioner has ever trained',
			actualPoint: 'It analyses gradient flow dynamics in wide two-layer neural networks.',
			kind: 'fresh',
			model: 'fixture',
			status: 'published',
			publishAt: at(-84 * HOUR)
		}
	],
	[
		{
			arxivId: '0000.00024',
			title: 'Pulsar Timing Residuals from a Twenty-Year Observing Campaign',
			abstract:
				'We report timing residuals from a twenty-year pulsar observing campaign. Three of the original observers have since retired.',
			authors: ['G. Mbeki', 'V. Solovyov', 'A. Dupont'],
			primaryCategory: 'astro-ph.HE',
			categories: ['astro-ph.HE', 'gr-qc'],
			publishedAt: at(-50 * DAY),
			absUrl: 'https://arxiv.org/abs/0000.00024'
		},
		{
			headline:
				'This Experiment Outlasted THREE Of Its Own Scientists. They Retired. It Continued.',
			dek: 'Twenty years. The pulsar is unaffected by staffing changes.',
			anchor: 'Three of the original observers have since retired',
			actualPoint: 'It reports pulsar timing residuals from a twenty-year observing campaign.',
			kind: 'vintage',
			model: 'fixture',
			status: 'published',
			publishAt: at(-92 * HOUR)
		}
	],
	[
		{
			arxivId: '0000.00025',
			title: 'Catalytic Conversion of Lignin Under Mild Aqueous Conditions',
			abstract:
				'We demonstrate catalytic conversion of lignin under mild aqueous conditions. Yields reached 62% at 140 degrees Celsius, which the authors describe as mild.',
			authors: ['F. Adeyinka', 'K. Brennan'],
			primaryCategory: 'physics.chem-ph',
			categories: ['physics.chem-ph'],
			publishedAt: at(-29 * DAY),
			absUrl: 'https://arxiv.org/abs/0000.00025'
		},
		{
			headline: 'Chemists Call 140 Degrees "MILD". What Else Are They Calling Mild?',
			dek: 'Well above boiling, described in print as gentle. Experts have not commented.',
			anchor: 'which the authors describe as mild',
			actualPoint: 'It demonstrates catalytic conversion of lignin at 62% yield in water.',
			kind: 'fresh',
			model: 'fixture',
			status: 'published',
			publishAt: at(-100 * HOUR)
		}
	],
	[
		{
			arxivId: '0000.00026',
			title: 'A Survey of Dwarf Galaxies in the Local Volume',
			abstract:
				'We survey dwarf galaxies within the local volume. Two candidate objects were discarded after being identified as internal reflections.',
			authors: ['I. Sato', 'R. Camargo'],
			primaryCategory: 'astro-ph.GA',
			categories: ['astro-ph.GA'],
			publishedAt: at(-38 * DAY),
			absUrl: 'https://arxiv.org/abs/0000.00026'
		},
		{
			headline: 'Astronomers Discovered Two Galaxies. They Were Reflections. Of The Telescope.',
			dek: 'Briefly, there were two more galaxies than there are. Then there were not.',
			anchor: 'identified as internal reflections',
			actualPoint: 'It surveys dwarf galaxies within the local volume.',
			kind: 'vintage',
			model: 'fixture',
			status: 'published',
			publishAt: at(-110 * HOUR)
		}
	],
	[
		{
			arxivId: '0000.00027',
			title: 'Static Analysis for Detecting Integer Overflow in Embedded C',
			abstract:
				'We present a static analyser for integer overflow in embedded C. Evaluated on 1.2 million lines of firmware from an anonymous washing machine vendor.',
			authors: ['M. Lindgren', 'S. Bhattacharya'],
			primaryCategory: 'cs.SE',
			categories: ['cs.SE', 'cs.PL'],
			publishedAt: at(-24 * DAY),
			absUrl: 'https://arxiv.org/abs/0000.00027'
		},
		{
			headline: 'Your Washing Machine Runs 1.2 MILLION Lines Of Code And The Vendor Is Anonymous',
			dek: 'They will not say whose washing machine. They analysed it anyway.',
			anchor: 'an anonymous washing machine vendor',
			actualPoint: 'It presents a static analyser for integer overflow in embedded C firmware.',
			kind: 'fresh',
			model: 'fixture',
			status: 'published',
			publishAt: at(-120 * HOUR)
		}
	],
	[
		{
			arxivId: '0000.00028',
			title: 'Phase Transitions in the Random Field Ising Model at Low Temperature',
			abstract:
				'We study phase transitions in the random field Ising model. The proof requires a multi-scale analysis carried out over 200 pages.',
			authors: ['L. Kowalczyk'],
			primaryCategory: 'math-ph',
			categories: ['math-ph', 'cond-mat.dis-nn'],
			publishedAt: at(-55 * DAY),
			absUrl: 'https://arxiv.org/abs/0000.00028'
		},
		{
			headline: 'A 200-PAGE Proof About Magnets Exists And You Have Never Read It',
			dek: 'Two hundred pages. About magnets. Somebody checked all of them.',
			anchor: 'a multi-scale analysis carried out over 200 pages',
			actualPoint:
				'It studies phase transitions in the random field Ising model at low temperature.',
			kind: 'vintage',
			model: 'fixture',
			status: 'published',
			publishAt: at(-130 * HOUR)
		}
	],
	[
		{
			arxivId: '0000.00029',
			title: 'Neural Decoding of Reach Direction from Motor Cortex',
			abstract:
				'We decode reach direction from motor cortex recordings. Data were collected from two macaques over 14 months, with sessions scheduled around their preferred nap times.',
			authors: ['A. Ferrante', 'W. Oyelowo'],
			primaryCategory: 'q-bio.NC',
			categories: ['q-bio.NC', 'cs.LG'],
			publishedAt: at(-19 * DAY),
			absUrl: 'https://arxiv.org/abs/0000.00029'
		},
		{
			headline: 'Neuroscience Is Being Scheduled Around Two Monkeys’ Nap Times',
			dek: 'Fourteen months of research, timetabled entirely at the animals’ convenience.',
			anchor: 'scheduled around their preferred nap times',
			actualPoint: 'It decodes reach direction from macaque motor cortex recordings.',
			kind: 'fresh',
			model: 'fixture',
			status: 'published',
			publishAt: at(-140 * HOUR)
		}
	],
	[
		{
			arxivId: '0000.00030',
			title: 'Tensor Network Contraction on Heterogeneous Hardware',
			abstract:
				'We optimise tensor network contraction across heterogeneous hardware. The scheduler occasionally produces plans that are optimal for reasons we do not fully understand.',
			authors: ['Q. Lin', 'D. Halvorsen'],
			primaryCategory: 'quant-ph',
			categories: ['quant-ph', 'cs.DC'],
			publishedAt: at(-21 * DAY),
			absUrl: 'https://arxiv.org/abs/0000.00030'
		},
		{
			headline:
				'Scientists Built Something That Works And Have Written Down That They Do Not Know Why',
			dek: 'It is optimal. They said so. They also said they cannot fully explain it.',
			anchor: 'optimal for reasons we do not fully understand',
			actualPoint:
				'It optimises tensor network contraction scheduling across heterogeneous hardware.',
			kind: 'fresh',
			model: 'fixture',
			status: 'published',
			publishAt: at(-150 * HOUR)
		}
	],
	[
		{
			arxivId: '0000.00031',
			title: 'Long-Term Monitoring of an Urban Bat Colony Using Acoustic Sensors',
			abstract:
				'We monitor an urban bat colony using acoustic sensors. The colony roosts in a municipal car park, level four, and has done so since at least 1998.',
			authors: ['E. Vasquez', 'T. Ademola'],
			primaryCategory: 'q-bio.PE',
			categories: ['q-bio.PE'],
			publishedAt: at(-33 * DAY),
			absUrl: 'https://arxiv.org/abs/0000.00031'
		},
		{
			headline: 'There Have Been Bats On Level Four Since 1998 And Nobody Told The Drivers',
			dek: 'Twenty-six years of undisclosed occupancy in a municipal car park.',
			anchor: 'a municipal car park, level four',
			actualPoint: 'It monitors an urban bat colony using long-term acoustic sensing.',
			kind: 'vintage',
			model: 'fixture',
			status: 'published',
			publishAt: at(-160 * HOUR)
		}
	]
];

for (const [paper, headline] of backCatalogue) {
	paperFixtures.push(paper);
	headlineFixtures.push({ ...headline, arxivId: paper.arxivId });
}
