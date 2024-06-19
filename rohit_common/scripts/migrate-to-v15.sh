nvm use v18

bench get-app hrms --branch version-15
bench get-app resilient-tech/india-compliance --branch version-15

echo "apps = frappe.get_installed_apps();apps.append('hrms');frappe.db.set_global('installed_apps', json.dumps(apps));frappe.clear_cache();print(frappe.get_installed_apps())" | bench console

bench reload-doc core doctype doctype
bench reload-doc integrations doctype webhook
bench reload-doc custom doctype doctype_layout
bench reload-doc desk doctype form_tour_step
bench reload-doc selling doctype selling_settings
bench reload-doc stock doctype repost_item_valuation
bench reload-doc setup doctype company
bench reload-doc accounts doctype payment_reconciliation_allocation

cd apps/frappe
git apply ../rohit_common/diffs/frappe-v15.diff

cd ../erpnext
git apply ../rohit_common/diffs/erpnext-v15.diff

cd ../..
bench migrate