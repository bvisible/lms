#//// Neoffice — added file (no upstream equivalent), d3b10e3f « un cours porte son
#//// article et sa table de durées ». Controller of the LMS Course Offer child table:
#//// one access duration and its price, so a single Item sells three months, a year or
#//// permanent access without multiplying articles — and without their descriptions
#//// drifting apart. At the merge: kept whole; the DocType JSON beside it is listed in
#//// NEOFFICE_FORK_MARKERS.md.
# Copyright (c) 2026, Neoffice and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class LMSCourseOffer(Document):
	"""Une durée d'accès et son prix — une ligne de la gamme d'un cours.

	Calquée sur `Booking Rate`, la table des forfaits d'une prestation
	réservable : le cours porte l'article, et la table porte les prix. Un cours
	se vend ainsi en trois mois, un an ou permanent sans qu'on multiplie les
	articles — et donc sans que leurs descriptions divergent.
	"""

	pass
