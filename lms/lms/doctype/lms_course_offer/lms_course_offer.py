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
