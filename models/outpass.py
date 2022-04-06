from odoo import fields, models, api, _
from datetime import datetime
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
from odoo import exceptions
import pytz
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError

UTC = pytz.utc
IST = pytz.timezone('Asia/Kolkata')


class GenerateOutPassRequest(models.Model):
    _inherit = 'generate.out.pass.request'

    def update_datas(self):
        total_ton = 0
        if len(self.order_lines_out_pass) == 0:
            raise exceptions.UserError('Please add Orders Lines before Issue the Out Pass')
        if sum(self.details_invoice_freight_lines.mapped('advance_amount')) > (
                self.env['advance.config'].search([])[-1]).amount:
            if self.approved_bool == False:
                raise exceptions.UserError('Advance Amount is greater than ' + str(
                    self.env['advance.config'].search([])[-1].amount) + ' Please get an approval form manager')
        for i in self.order_lines_out_pass:
            total_ton = total_ton + i.ton
        if total_ton == self.total_vehicle_capacity_needed:

            # Purchase Details For External Company
            if self.vehicle_id.company_type == 'external':
                if self.purchase_id.id:
                    for purline in self.purchase_id.order_line:
                        purline.unlink()
                    for vehilces in self.order_lines_out_pass:
                        self.env['purchase.order.line'].create({
                            'order_id': self.purchase_id.id,
                            'product_id': self.env['product.product'].search([('name', '=', 'Rental of Vehicle')]).id,
                            'name': 'Freight',
                            'date_planned': datetime.now().date(),
                            'product_qty': vehilces.ton,
                            'price_unit': vehilces.own_rate,
                            'price_subtotal': vehilces.ton * vehilces.own_rate,
                            'product_uom': self.env['uom.uom'].search([('name', '=', 'Units')]).id,
                        })

            # Fuel Details
            length_petrol_lines = len(self.details_invoice_freight_lines)
            petrol_price = sum(self.details_invoice_freight_lines.mapped('petrol_price')) / length_petrol_lines
            petrol_qty = sum(self.details_invoice_freight_lines.mapped('petrol_qty')) / length_petrol_lines
            petrol_rate = sum(self.details_invoice_freight_lines.mapped('petrol_rate')) / length_petrol_lines

            for fuel in self.details_invoice_freight_lines:
                self.petrol_rec_id.update({
                    'date': self.petrol_rec_id.date,
                    'bunk_id': fuel.petrol_bunk.id,
                    'fuel_rate': fuel.petrol_rate,
                    'fuel_quantity': fuel.petrol_qty,
                    'to_reimberse': fuel.petrol_price,
                    'vehicle_id': fuel.vehicle_id.id,
                    'status': 'draft',
                    'type': fuel.petrol_bunk.type,
                    'petrol_id': self.pumb_payment_id.id,
                    'ind_no': fuel.ind_no
                })

                if fuel.petrol_bunk.type == 'Internal':
                    if self.expense_id.id:
                        self.expense_id.unlink()
                    if self.pumb_payment_id.id:
                        self.pumb_payment_id.update({
                            'date': self.invoice_date,
                            'description': 'For Fuel/' + str(
                                self.invoice_date) + '/' + fuel.vehicle_id.name,
                            'vehicle_id': fuel.vehicle_id.id,
                            'bunk_id': fuel.petrol_bunk.id,
                            'bunk_owner': fuel.petrol_bunk.partner_details.id,
                            'branch_id': self.env.user.branch_id.id,
                            'vehicle_req': self.vehicle_req.id,
                            'employee': self.env.user.id,
                            'fuel_id': fuel.vehicle_id.fuel_type.product_id.id,
                            'price': fuel.petrol_rate,
                            'quantity': fuel.petrol_qty,
                            'total': fuel.petrol_price,
                            'state': 'draft',
                            'ind_no': fuel.ind_no,
                            'outpass_id': self.id,
                        })
                    else:
                        internal_bunk_record = self.env['internal.pumb.payment'].create({
                            'date': self.invoice_date,
                            'description': 'For Fuel/' + str(datetime.now().date()) + '/' + fuel.vehicle_id.name,
                            'vehicle_id': fuel.vehicle_id.id,
                            'bunk_id': fuel.petrol_bunk.id,
                            'bunk_owner': fuel.petrol_bunk.partner_details.id,
                            'branch_id': self.env.user.branch_id.id,
                            'vehicle_req': self.vehicle_req.id,
                            'employee': self.env.user.id,
                            'fuel_id': fuel.vehicle_id.fuel_type.product_id.id,
                            'price': fuel.petrol_rate,
                            'quantity': fuel.petrol_qty,
                            'total': fuel.petrol_price,
                            'state': 'draft',
                            'ind_no': fuel.ind_no,
                            'outpass_id': self.id,
                        })
                        self.pumb_payment_id = internal_bunk_record.id
                        if fuel.vehicle_id.mark_internal == True:
                            internal_fuel_sale_id = self.env['internal.vehicle.sales'].create({
                                'date': self.invoice_date,
                                'customer_id': self.env.user.company_id.partner_id.id,
                                'vehicle_id': fuel.vehicle_id.petrol_vehicle_id.id,
                                'product_id': fuel.vehicle_id.fuel_type.id,
                                'quantity': fuel.petrol_qty,
                                'unit_price': fuel.petrol_rate,
                                'price_subtotal': fuel.petrol_rate * fuel.petrol_qty,
                                'ind_no': fuel.ind_no,
                                'state': 'draft'
                            })
                            self.internal_fuel_sale_id = internal_fuel_sale_id.id
                        else:
                            raise UserError('Please Mark the Vehicle as Internal')

                if fuel.petrol_bunk.type == 'External':
                    if self.pumb_payment_id.id:
                        self.pumb_payment_id.unlink()
                    company_id = self.env['res.company']
                    bunk_owner = self.env['res.partner']
                    if fuel.petrol_bunk.type == 'Internal':
                        bunk_owner = fuel.petrol_bunk.partner_details.id
                        company_id = fuel.petrol_bunk.owner_id.id
                    else:
                        company_id = self.env.user.company_id.id
                        bunk_owner = fuel.petrol_bunk.owner_name.id
                    if self.expense_id.id:
                        if self.expense_id.unit_amount != fuel.petrol_price:
                            print('value')
                            self.expense_id.update({
                                'name': 'For Petrol/' + str(self.invoice_date) + '/' + fuel.vehicle_id.name,
                                'vehicle_id': fuel.vehicle_id.id,
                                'vehicle_req': self.vehicle_req.id,
                                'owner_name': fuel.owner,
                                'bunk_owner': bunk_owner,

                                'quantity': 1,
                                'mtc_expense': True,
                                'from_company': self.env.user.company_id.id,
                                'company_id': self.env.user.company_id.id,
                                'product_id': (
                                    self.env['product.template'].search([('name', '=', 'Expenses')])).product_variant_id.id,
                                'payment_mode': 'company_account',
                                'exp_branch': self.env.user.branch_id.id,
                                # 'outpass_id': self.id,
                                'unit_amount': fuel.petrol_price,
                            })
                    else:
                        expense = self.env['hr.expense'].create({
                            'name': 'For Petrol/' + str(self.invoice_date) + '/' + fuel.vehicle_id.name,
                            'vehicle_id': fuel.vehicle_id.id,
                            'vehicle_req': self.vehicle_req.id,
                            'owner_name': fuel.owner,
                            'bunk_owner': bunk_owner,
                            'unit_amount': fuel.petrol_price,
                            'quantity': 1,
                            'mtc_expense': True,
                            'from_company': self.env.user.company_id.id,
                            'company_id': self.env.user.company_id.id,
                            'product_id': (
                                self.env['product.template'].search([('name', '=', 'Expenses')])).product_variant_id.id,
                            'payment_mode': 'company_account',
                            'exp_branch': self.env.user.branch_id.id,
                            # 'outpass_id': self.id,
                            'date': self.invoice_date,
                        })
                        self.expense_id = expense.id

            # Order Line Details Updation
            for order_line in self.order_lines_out_pass:
                # Freight Record Updation
                order_line.freight_rec_id.update({
                    'company_name': self.env.user.company_id.id,
                    'partner_id': order_line.vehicle_req.customer.id,
                    'vehicle_req': self.vehicle_req.id,
                    'branch_id': self.env.user.branch_id.id,
                    'bill_no': order_line.invoice_no,
                    'bill_date': order_line.invoice_date,
                    'product_id': order_line.material_description.id,
                    'product_uom_qty': order_line.ton,
                    'product_uom': self.env['uom.uom'].search([('name', '=', 'Ton')]).id,
                    'price_unit': order_line.company_rate,
                    'price_subtotal': order_line.company_rate * order_line.ton,
                    'actual_total': order_line.company_rate * order_line.ton,
                    'invoice_date': self.invoice_date,
                    'company_id': self.env.user.company_id.id,
                    'request_type': self.vehicle_req.request_type,
                    'location': order_line.place_from,
                    'destination': order_line.place_to,
                    'from_date': self.vehicle_req.request_date,
                    'to_date': self.vehicle_req.delivery_date,
                    'status': 'outpass pending'
                })

                # Dispatch Record Updation
                firm = None
                vehicle_type = None
                if order_line.vehicle_id.company_type == 'external':
                    vehicle_type = 'external'
                if order_line.vehicle_id.company_type == 'internal':
                    vehicle_type = 'internal'
                    firm = order_line.vehicle_id.internal_comapny.id
                order_line.dispatch_rec_id.update({
                    'order_id': order_line.id,
                    'vehicle_req': self.vehicle_req.id,
                    'vehicle_id': order_line.vehicle_id.id,
                    'invoice_no': order_line.invoice_no,
                    'company_name': order_line.company_name.id,
                    'invoice_date': order_line.invoice_date,
                    'm_code': order_line.m_code.name,
                    'material_description': order_line.material_description.id,
                    'place_from': order_line.place_from,
                    'place_to': order_line.place_to,
                    'party_name': order_line.party_name,
                    'ton': order_line.ton,
                    'own_rate': order_line.own_rate,
                    'company_rate': order_line.company_rate,
                    'company_total': order_line.company_total,
                    'mamool': order_line.mamool,
                    'loading_charge': order_line.loading_charge,
                    'req_branch': self.req_branch.id,
                    'current_branch': self.current_branch.id,
                    'requested_date': self.requested_date,
                    'external': vehicle_type,
                    'firm_id': firm
                })

                # Mamool Sale
                mamool_line = self.env['sale.order.line'].search([('order_id', '=', order_line.sale_id_mamool.id)])
                if mamool_line:
                    mamool_line.update({'price_unit': order_line.mamool,
                                        'product_uom_qty': 1})

                # Loading Sale
                loading_line = self.env['sale.order.line'].search([('order_id', '=', order_line.sale_id_loading.id)])
                if loading_line:
                    loading_line.update({
                        'price_unit': order_line.loading_charge,
                        'product_uom_qty': 1
                    })

            # Advanvce Details
            advance = sum(self.details_invoice_freight_lines.mapped('advance_amount'))

            # Mamool Amount
            mamool = sum(self.order_lines_out_pass.mapped('mamool'))
            if self.vehicle_id.company_type == 'external':
                self.mamool_id.update({
                    'amount': mamool, })

            # Load Charge
            loading_charge = sum(self.order_lines_out_pass.mapped('loading_charge'))
            if self.vehicle_id.company_type == 'external':
                self.loading_id.update({
                    'amount': loading_charge, })

            trip = self.env['trip.sheet.lines'].search([('name', '=', self.trip_id.id), ('outpass', '=', True)])
            betta = self.env['betta.lines'].search([('trip_id', '=', self.trip_id.id), ('outpass', '=', True)])
            for tripline in trip:
                tripline.unlink()
            for bettaline in betta:
                bettaline.unlink()
            trip_list = []
            betta_list = []
            real_rate = 0.0
            company_rate = 0.0
            real_ton = 0.0
            current_rate = 0.0
            freight_list = []
            invoice_number_list = []
            for invoice_line in self.order_lines_out_pass:
                if invoice_line.vehicle_id.company_type == 'external':
                    real_ton = real_ton + invoice_line.ton
                    current_rate = invoice_line.own_rate
                    real_rate = real_rate + invoice_line.own_rate * invoice_line.ton
                    freight_list.append(str(invoice_line.ton) + ' Ton - Per Ton ' + str(invoice_line.own_rate))
                    invoice_number_list.append(invoice_line.invoice_no)
                if invoice_line.vehicle_id.company_type != 'external':
                    real_ton = real_ton + invoice_line.ton
                    current_rate = invoice_line.company_rate
                    real_rate = real_rate + invoice_line.company_rate * invoice_line.ton
                    freight_list.append(str(invoice_line.ton) + ' Ton - Per Ton ' + str(invoice_line.own_rate))
                    invoice_number_list.append(invoice_line.invoice_no)
                company_rate = company_rate + invoice_line.company_rate * invoice_line.ton
            trip_list_line = (0, 0, {
                'description': 'Freight for ' + str(freight_list),
                'total_freight': real_rate,
                'real_rate': real_rate,
                'company_freight': company_rate,
                'line_type': 'freight',
                'outpass': True,
            })
            trip_list.append(trip_list_line)

            for fuel_lines in self.details_invoice_freight_lines:
                if fuel_lines.petrol_bunk.type == 'Internal':
                    trip_list_line = (0, 0, {
                        'description': 'Petrol Price',
                        'reimbursed_expenses': fuel_lines.petrol_price,
                        'petrol_id': self.pumb_payment_id.id,
                        'line_type': 'petrol',
                        'outpass': True
                    })
                    trip_list.append(trip_list_line)
                if fuel_lines.petrol_bunk.type == 'External':
                    trip_list_line = (0, 0, {
                        'description': 'Petrol Price',
                        'reimbursed_expenses': fuel_lines.petrol_price,
                        'expense_id': self.expense_id.id,
                        'line_type': 'petrol',
                        'outpass': True
                    })
                    trip_list.append(trip_list_line)
                if fuel_lines.advance_amount > 0:
                    trip_list_line = (0, 0, {
                        'description': 'Advance Paid',
                        'given': fuel_lines.advance_amount,
                        'line_type': 'advance',
                        'outpass': True
                    })
                    trip_list.append(trip_list_line)
                    betta_list_line = (0, 0, {
                        'description': 'Advance Paid',
                        'advance': fuel_lines.advance_amount,
                        'line_type': 'advance',
                        'outpass': True,
                    })
                    betta_list.append(betta_list_line)
            for order_lines in self.order_lines_out_pass:
                if order_lines.mamool > 0:
                    trip_list_line = (0, 0, {
                        'description': 'Mamool/' + order_lines.invoice_no,
                        'given': order_lines.mamool,
                        'sale_order': [(order_lines.sale_id_mamool.id)],
                        'line_type': 'mamool',
                        'outpass': True,
                    })
                    trip_list.append(trip_list_line)
                if order_lines.loading_charge > 0:
                    trip_list_line = (0, 0, {
                        'description': 'Loading Price/' + order_lines.invoice_no,
                        'given': order_lines.loading_charge,
                        'sale_order': [(order_lines.sale_id_loading.id)],
                        'line_type': 'loading charge',
                        'outpass': True,
                    })
                    trip_list.append(trip_list_line)

            self.trip_id.update({
                'vehicle_trip_sheet_lines': trip_list,
                'betta_lines': betta_list
            })

            if advance > 0:
                if self.advance_cash_id.id:
                    if self.advance_cash_id.credit != 0:
                        old_advance = self.advance_cash_id.credit
                        self.advance_cash_id.credit = advance + loading_charge + mamool
                        if datetime.now(IST).date() == self.advance_cash_id.date:
                            closing = self.env['cash.transfer.record.register'].search(
                                [('date', '=', self.advance_cash_id.date), ('closing_bool', '=', True,),
                                 ('branch_id', '=', self.env.user.branch_id.id),
                                 ('company_id', '=', self.env.user.company_id.id)])
                            # opening = self.env['cash.transfer.record.register'].search(
                            #     [('date', '=', self.advance_cash_id.date + relativedelta(days=1)),
                            #      ('opening_bool', '=', True,), ('branch_id', '=', self.env.user.branch_id.id),
                            #      ('company_id', '=', self.env.user.company_id.id)])
                            if closing:
                                # if opening:
                                closing.credit = closing.credit - old_advance
                                # opening.credit = closing.credit - old_advance
                                closing.total = closing.total - old_advance
                                 # opening.total = opening.total - old_advance
                        else:
                            if datetime.now(IST).date() > self.advance_cash_id.date:
                                daylenght = (datetime.now(IST).date() - self.advance_cash_id.date).days
                                for days in range(0, daylenght + 1):
                                    print('Days',days)
                                    closing = self.env['cash.transfer.record.register'].search(
                                        [('date', '=', (datetime.now(IST).date() - relativedelta(days=days))),
                                         ('closing_bool', '=', True,),
                                         ('branch_id', '=', self.env.user.branch_id.id),
                                         ('company_id', '=', self.env.user.company_id.id)])
                                    opening = self.env['cash.transfer.record.register'].search(
                                        [('date', '=',
                                          (datetime.now(IST).date() - relativedelta(days=days))),
                                         ('opening_bool', '=', True,), ('branch_id', '=', self.env.user.branch_id.id),
                                         ('company_id', '=', self.env.user.company_id.id)])
                                    if self.advance_cash_id.date != (datetime.now(IST).date() - relativedelta(days=days)):
                                        if closing:
                                            closing.total = closing.total + self.advance_cash_id.credit
                                            closing.opening_balance = closing.opening_balance + self.advance_cash_id.credit
                                        if opening:
                                            opening.total = opening.total + self.advance_cash_id.credit
                                            opening.opening_balance = opening.opening_balance + self.advance_cash_id.credit
                                    if self.advance_cash_id.date == (datetime.now(IST).date() - relativedelta(days=days)):
                                        if closing:
                                            closing.total = closing.total + self.advance_cash_id.credit
                                            closing.credit = closing.credit - self.advance_cash_id.credit
                    self.advance_cash_id.unlink()
                else:
                    # for loading_l in self.details_invoice_freight_lines:
                    total_amt = advance + loading_charge + mamool
                    if total_amt > 0:
                        opening_balance = self.env['cash.transfer.record.register'].search(
                            [('opening_bool', '=', True), ('date', '=', self.invoice_date)])
                        if not opening_balance:
                            self.env['cash.transfer.record.register'].create({
                                'date': self.invoice_date,
                                'name': 'Opening Balance',
                                'branch_id': self.env.user.branch_id.id,
                                'company_id': self.env.user.company_id.id,
                                'opening_balance': 0,
                                'opening_bool': True,
                                'status': 'open',
                            })
                            self.env['cash.transfer.record.register'].create({
                                'date': self.invoice_date,
                                'name': 'Closing Balance',
                                'branch_id': self.env.user.branch_id.id,
                                'company_id': self.env.user.company_id.id,
                                'opening_balance': 0,
                                'closing_bool': True,
                                'status': 'close',
                            })

                        self.advance_cash_id = self.env['cash.transfer.record.register'].create({
                            'date': self.invoice_date,
                            'name': 'Advance For Vehicle Request ' + self.vehicle_req.name + ' For Vehicle No(' + self.vehicle_id.license_plate + ')-',
                            'credit': total_amt,
                            'branch_id': self.env.user.branch_id.id,
                            'company_id': self.env.user.company_id.id,
                            'status': 'open',
                            'transactions': True,
                            'transaction_type': 'advance',
                        }).id
                        credit_cash = total_amt
                        # if not opening_balance:
                        closing_balance = self.env['cash.transfer.record.register'].search(
                            [('branch_id', '=', self.env.user.branch_id.id), ('closing_bool', '=', True),
                             ('date', '=', self.invoice_date)])
                        if closing_balance:
                            closing_balance.credit = closing_balance.credit + credit_cash
                            closing_balance.total = closing_balance.total - credit_cash

                        current_date = datetime.now(IST).date()
                        day_lenght = (current_date - self.invoice_date).days
                        if day_lenght != 0:
                            programming_date_back = self.invoice_date
                            for days in range(1, day_lenght + 1):
                                programming_date = self.invoice_date + relativedelta(days=days)
                                old_closing_balance = self.env['cash.transfer.record.register'].search(
                                    [('branch_id', '=', self.env.user.branch_id.id), ('closing_bool', '=', True),
                                     ('date', '=', programming_date_back)])
                                new_opening_balance = self.env['cash.transfer.record.register'].search(
                                    [('branch_id', '=', self.env.user.branch_id.id), ('opening_bool', '=', True),
                                     ('date', '=', programming_date)])
                                if old_closing_balance:
                                    if new_opening_balance:
                                        new_opening_balance.opening_balance = old_closing_balance.total
                                        new_opening_balance.total = (
                                                                            new_opening_balance.opening_balance + new_opening_balance.debit) - new_opening_balance.credit
                                    else:
                                        self.env['cash.transfer.record.register'].create({
                                            'date': programming_date,
                                            'name': 'Opening Balance',
                                            'branch_id': self.env.user.branch_id.id,
                                            'company_id': self.env.user.company_id.id,
                                            'opening_balance': old_closing_balance.total,
                                            'total': old_closing_balance.total,
                                            'opening_bool': True,
                                            'status': 'open',
                                        })
                                today_opening_balance = self.env['cash.transfer.record.register'].search(
                                    [('branch_id', '=', self.env.user.branch_id.id), ('opening_bool', '=', True),
                                     ('date', '=', programming_date)])
                                new_closing_balance = self.env['cash.transfer.record.register'].search(
                                    [('branch_id', '=', self.env.user.branch_id.id), ('closing_bool', '=', True),
                                     ('date', '=', programming_date)])
                                if new_closing_balance:
                                    new_closing_balance.opening_balance = today_opening_balance.total
                                    new_closing_balance.total = (
                                                                        new_closing_balance.opening_balance + new_closing_balance.debit) - new_closing_balance.credit
                                else:
                                    self.env['cash.transfer.record.register'].create({
                                        'date': programming_date,
                                        'name': 'Closing Balance',
                                        'branch_id': self.env.user.branch_id.id,
                                        'company_id': self.env.user.company_id.id,
                                        'opening_balance': old_closing_balance.total,
                                        'total': old_closing_balance.total,
                                        'closing_bool': True,
                                        'status': 'close',
                                    })
                                programming_date_back = programming_date

            if mamool > 0:
                if self.mamool_cash_id.debit != 0:
                    # self.mamool_cash_id.debit = mamool
                    if datetime.now(IST).date() == self.mamool_cash_id.date:
                        closing = self.env['cash.transfer.record.register'].search(
                            [('date', '=', self.mamool_cash_id.date), ('closing_bool', '=', True,),
                             ('branch_id', '=', self.env.user.branch_id.id),
                             ('company_id', '=', self.env.user.company_id.id)])
                        # opening = self.env['cash.transfer.record.register'].search(
                        #     [('date', '=', self.mamool_cash_id.date + relativedelta(days=1)),
                        #      ('opening_bool', '=', True,), ('branch_id', '=', self.env.user.branch_id.id),
                        #      ('company_id', '=', self.env.user.company_id.id)])
                        if closing:
                            # if opening:
                            closing.debit = closing.debit - self.mamool_cash_id.debit
                            # opening.credit = closing.debit - self.mamool_cash_id.debit
                            closing.total = closing.total - self.mamool_cash_id.debit
                            # opening.total = opening.total - self.mamool_cash_id.debit
                        # if closing:
                        #     if opening:
                        #         closing.credit = closing.credit - advance
                        #         opening.credit = closing.credit - advance
                        #         closing.total = closing.total - advance
                        #         opening.total = opening.total - advance
                    else:
                        if datetime.now(IST).date() > self.mamool_cash_id.date:
                            daylenght = (datetime.now(IST).date() - self.mamool_cash_id.date).days
                            for days in range(0, daylenght + 1):
                                closing = self.env['cash.transfer.record.register'].search(
                                    [('date', '=', datetime.now(IST).date() - relativedelta(days=days)),
                                     ('closing_bool', '=', True,),
                                     ('branch_id', '=', self.env.user.branch_id.id),
                                     ('company_id', '=', self.env.user.company_id.id)])
                                opening = self.env['cash.transfer.record.register'].search(
                                    [('date', '=',
                                      datetime.now(IST).date() - relativedelta(days=days)),
                                     ('opening_bool', '=', True,), ('branch_id', '=', self.env.user.branch_id.id),
                                     ('company_id', '=', self.env.user.company_id.id)])
                                if self.mamool_cash_id.date != datetime.now(IST).date() - relativedelta(days=days):
                                    if closing:
                                        closing.total = closing.total - self.mamool_cash_id.debit
                                        closing.opening_balance = closing.opening_balance - self.mamool_cash_id.debit
                                    if opening:
                                        opening.total = opening.total - self.mamool_cash_id.debit
                                        opening.opening_balance = opening.opening_balance - self.mamool_cash_id.debit
                                if self.mamool_cash_id.date == datetime.now(IST).date() - relativedelta(days=days):
                                    if closing:
                                        closing.total = closing.total - self.mamool_cash_id.debit
                                        closing.debit = closing.debit - self.mamool_cash_id.debit
                    self.mamool_cash_id.unlink()

            if loading_charge > 0:
                if self.loading_cash_id.debit != 0:
                    # self.loading_cash_id.debit = loading_charge
                    if datetime.now(IST).date() == self.loading_cash_id.date:
                        closing = self.env['cash.transfer.record.register'].search(
                            [('date', '=', self.loading_cash_id.date), ('closing_bool', '=', True,),
                             ('branch_id', '=', self.env.user.branch_id.id),
                             ('company_id', '=', self.env.user.company_id.id)])
                        # opening = self.env['cash.transfer.record.register'].search(
                        #     [('date', '=', self.loading_cash_id.date + relativedelta(days=1)),
                        #      ('opening_bool', '=', True,), ('branch_id', '=', self.env.user.branch_id.id),
                        #      ('company_id', '=', self.env.user.company_id.id)])
                        if closing:
                            # if opening:
                            closing.debit = closing.debit - self.loading_cash_id.debit
                            # opening.credit = closing.debit - self.loading_cash_id.debit
                            closing.total = closing.total - self.loading_cash_id.debit
                            # opening.total = opening.total - self.loading_cash_id.debit
                    else:
                        if datetime.now(IST).date() > self.loading_cash_id.date:
                            daylenght = (datetime.now(IST).date() - self.loading_cash_id.date).days
                            for days in range(0, daylenght + 1):
                                closing = self.env['cash.transfer.record.register'].search(
                                    [('date', '=', datetime.now(IST).date() - relativedelta(days=days)),
                                     ('closing_bool', '=', True,),
                                     ('branch_id', '=', self.env.user.branch_id.id),
                                     ('company_id', '=', self.env.user.company_id.id)])
                                opening = self.env['cash.transfer.record.register'].search(
                                    [('date', '=',
                                      datetime.now(IST).date() - relativedelta(days=days)),
                                     ('opening_bool', '=', True,), ('branch_id', '=', self.env.user.branch_id.id),
                                     ('company_id', '=', self.env.user.company_id.id)])
                                if self.loading_cash_id.date != datetime.now(IST).date() - relativedelta(days=days):
                                    if closing:
                                        closing.total = closing.total - self.loading_cash_id.debit
                                        closing.opening_balance = closing.opening_balance - self.loading_cash_id.debit
                                    if opening:
                                        opening.total = opening.total - self.loading_cash_id.debit
                                        opening.opening_balance = opening.opening_balance - self.loading_cash_id.debit
                                if self.loading_cash_id.date == datetime.now(IST).date() - relativedelta(days=days):
                                    if closing:
                                        closing.total = closing.total - self.loading_cash_id.debit
                                        closing.debit = closing.debit - self.loading_cash_id.debit
                    self.loading_cash_id.unlink()
            lorry_advance = advance + mamool + loading_charge
            if lorry_advance > 0:
                # company_payment_id = self.env['account.account'].search(
                #     [('name', '=', 'Cash'), ('company_id', '=', self.env.user.company_id.id)]).id
                # cash_id = self.env['account.journal'].search(
                #     [('name', '=', 'Cash'), ('company_id', '=', self.env.user.company_id.id)]).id
                #
                # journal_list_1 = []
                # journal_line_two = (0, 0, {
                #     'account_id': company_payment_id,
                #     'name': 'Advance Payment For Vehicle Request' + self.vehicle_req.name + ' For Vehicle No(' + t.vehicle_id.license_plate + ')',
                #     'debit': lorry_advance,
                # })
                # journal_list_1.append(journal_line_two)
                # journal_line_one = (0, 0, {
                #     'account_id': self.env['branch.account'].search(
                #         [('name', '=', self.env.user.branch_id.id)]).account_id.id,
                #     'name': 'Advance Payment For Vehicle Request ' + self.vehicle_req.name + ' For Vehicle No(' + t.vehicle_id.license_plate + ')',
                #     'credit': lorry_advance,
                # })
                # journal_list_1.append(journal_line_one)
                # journal_id_1 = self.env['account.move'].create({
                #     'date': datetime.now().date(),
                #     'ref': 'Advance Payment For Vehicle Request ' + self.vehicle_req.name + ' For Vehicle No(' + t.vehicle_id.license_plate + ')',
                #     'journal_id': cash_id,
                #     'line_ids': journal_list_1,
                # })
                # journal_id_1.action_post()

                # code for Cash Book Balancing
                opening_balance = self.env['cash.transfer.record.register'].search(
                    [('opening_bool', '=', True), ('date', '=', self.invoice_date)])
                if not opening_balance:
                    self.env['cash.transfer.record.register'].create({
                        'date': self.invoice_date,
                        'name': 'Opening Balance',
                        'branch_id': self.env.user.branch_id.id,
                        'company_id': self.env.user.company_id.id,
                        'opening_balance': 0,
                        'opening_bool': True,
                        'status': 'open',
                    })
                    self.env['cash.transfer.record.register'].create({
                        'date': self.invoice_date,
                        'name': 'Closing Balance',
                        'branch_id': self.env.user.branch_id.id,
                        'company_id': self.env.user.company_id.id,
                        'opening_balance': 0,
                        'closing_bool': True,
                        'status': 'close',
                    })

                self.advance_cash_id = self.env['cash.transfer.record.register'].create({
                    'date': self.invoice_date,
                    'name': 'Advance For Vehicle Request ' + self.vehicle_req.name + ' For Vehicle No(' + self.vehicle_id.license_plate + ')-',
                    'credit': lorry_advance,
                    'branch_id': self.env.user.branch_id.id,
                    'company_id': self.env.user.company_id.id,
                    'status': 'open',
                    'transactions': True,
                    'transaction_type': 'advance',
                }).id
                credit_cash = lorry_advance
                # if not opening_balance:
                closing_balance = self.env['cash.transfer.record.register'].search(
                    [('branch_id', '=', self.env.user.branch_id.id), ('closing_bool', '=', True),
                     ('date', '=', self.invoice_date)])
                if closing_balance:
                    closing_balance.credit = closing_balance.credit + credit_cash
                    closing_balance.total = closing_balance.total - credit_cash

                current_date = datetime.now(IST).date()
                day_lenght = (current_date - self.invoice_date).days
                if day_lenght != 0:
                    programming_date_back = self.invoice_date
                    for days in range(1, day_lenght + 1):
                        programming_date = self.invoice_date + relativedelta(days=days)
                        old_closing_balance = self.env['cash.transfer.record.register'].search(
                            [('branch_id', '=', self.env.user.branch_id.id), ('closing_bool', '=', True),
                             ('date', '=', programming_date_back)])
                        new_opening_balance = self.env['cash.transfer.record.register'].search(
                            [('branch_id', '=', self.env.user.branch_id.id), ('opening_bool', '=', True),
                             ('date', '=', programming_date)])
                        if old_closing_balance:
                            if new_opening_balance:
                                new_opening_balance.opening_balance = old_closing_balance.total
                                new_opening_balance.total = (
                                                                    new_opening_balance.opening_balance + new_opening_balance.debit) - new_opening_balance.credit
                            else:
                                self.env['cash.transfer.record.register'].create({
                                    'date': programming_date,
                                    'name': 'Opening Balance',
                                    'branch_id': self.env.user.branch_id.id,
                                    'company_id': self.env.user.company_id.id,
                                    'opening_balance': old_closing_balance.total,
                                    'total': old_closing_balance.total,
                                    'opening_bool': True,
                                    'status': 'open',
                                })
                        today_opening_balance = self.env['cash.transfer.record.register'].search(
                            [('branch_id', '=', self.env.user.branch_id.id), ('opening_bool', '=', True),
                             ('date', '=', programming_date)])
                        new_closing_balance = self.env['cash.transfer.record.register'].search(
                            [('branch_id', '=', self.env.user.branch_id.id), ('closing_bool', '=', True),
                             ('date', '=', programming_date)])
                        if new_closing_balance:
                            new_closing_balance.opening_balance = today_opening_balance.total
                            new_closing_balance.total = (
                                                                new_closing_balance.opening_balance + new_closing_balance.debit) - new_closing_balance.credit
                        else:
                            self.env['cash.transfer.record.register'].create({
                                'date': programming_date,
                                'name': 'Closing Balance',
                                'branch_id': self.env.user.branch_id.id,
                                'company_id': self.env.user.company_id.id,
                                'opening_balance': old_closing_balance.total,
                                'total': old_closing_balance.total,
                                'closing_bool': True,
                                'status': 'close',
                            })
                        programming_date_back = programming_date
                # if self.vehicle_id.company_type == 'external':
                #     if lorry_advance > 0:
                #         print('Company', self.env.user.company_id.id)
                #         inv_paid = self.env['account.payment.register'].with_context(active_model='account.move',
                #                                                                        active_ids=inv.ids).create({
                #             'payment_date': inv.date,
                #             'journal_id': self.env['account.journal'].search(
                #                 [('name', '=', 'Cash'), ('company_id', '=', self.env.user.company_id.id)]).id,
                #             'payment_method_id':1,
                #             'amount': lorry_advance,
                #
                #         })
                #         inv_paid._create_payments()
            lorry_mamool = mamool
            if lorry_mamool > 0:
                # company_payment_id = self.env['account.account'].search(
                #     [('name', '=', 'Cash'), ('company_id', '=', self.env.user.company_id.id)]).id
                # cash_id = self.env['account.journal'].search(
                #     [('name', '=', 'Cash'), ('company_id', '=', self.env.user.company_id.id)]).id
                #
                # journal_list_1 = []
                # journal_line_two = (0, 0, {
                #     'account_id': company_payment_id,
                #     'name': 'Mamool For Vehicle Request' + self.vehicle_req.name + ' For Vehicle No(' + t.vehicle_id.license_plate + ')',
                #     'credit': lorry_mamool,
                # })
                # journal_list_1.append(journal_line_two)
                # journal_line_one = (0, 0, {
                #     'account_id': self.env['branch.account'].search(
                #         [('name', '=', self.env.user.branch_id.id)]).account_id.id,
                #     'name': 'Mamool For Vehicle Request ' + self.vehicle_req.name + ' For Vehicle No(' + t.vehicle_id.license_plate + ')',
                #     'debit': lorry_mamool,
                # })
                # journal_list_1.append(journal_line_one)
                # journal_id_1 = self.env['account.move'].create({
                #     'date': datetime.now().date(),
                #     'ref': 'Mamool For Vehicle Request ' + self.vehicle_req.name + ' For Vehicle No(' + t.vehicle_id.license_plate + ')',
                #     'journal_id': cash_id,
                #     'line_ids': journal_list_1,
                # })
                # journal_id_1.action_post()

                # code for Cash Book Balancing
                opening_balance = self.env['cash.transfer.record.register'].search(
                    [('opening_bool', '=', True), ('date', '=', self.invoice_date)])
                if not opening_balance:
                    self.env['cash.transfer.record.register'].create({
                        'date': self.invoice_date,
                        'name': 'Opening Balance',
                        'branch_id': self.env.user.branch_id.id,
                        'company_id': self.env.user.company_id.id,
                        'opening_balance': 0,
                        'opening_bool': True,
                        'status': 'open',
                    })
                    self.env['cash.transfer.record.register'].create({
                        'date': self.invoice_date,
                        'name': 'Closing Balance',
                        'branch_id': self.env.user.branch_id.id,
                        'company_id': self.env.user.company_id.id,
                        'opening_balance': 0,
                        'closing_bool': True,
                        'status': 'close',
                    })

                self.mamool_cash_id = self.env['cash.transfer.record.register'].create({
                    'date': self.invoice_date,
                    'name': 'Mamool For Vehicle Request ' + self.vehicle_req.name + ' For Vehicle No(' + self.vehicle_id.license_plate + ')',
                    'debit': lorry_mamool,
                    'branch_id': self.env.user.branch_id.id,
                    'company_id': self.env.user.company_id.id,
                    'status': 'open',
                    'transactions': True,
                    'transaction_type': 'mamool'
                }).id
                debit_cash = lorry_mamool
                # if not opening_balance:
                closing_balance = self.env['cash.transfer.record.register'].search(
                    [('branch_id', '=', self.env.user.branch_id.id), ('closing_bool', '=', True),
                     ('date', '=', self.invoice_date)])
                if closing_balance:
                    closing_balance.debit = closing_balance.debit + debit_cash
                    closing_balance.total = closing_balance.total + debit_cash

                current_date = datetime.now(IST).date()
                day_lenght = (current_date - self.invoice_date).days
                if day_lenght != 0:
                    programming_date_back = self.invoice_date
                    for days in range(1, day_lenght + 1):
                        programming_date = self.invoice_date + relativedelta(days=days)
                        old_closing_balance = self.env['cash.transfer.record.register'].search(
                            [('branch_id', '=', self.env.user.branch_id.id), ('closing_bool', '=', True),
                             ('date', '=', programming_date_back)])
                        new_opening_balance = self.env['cash.transfer.record.register'].search(
                            [('branch_id', '=', self.env.user.branch_id.id), ('opening_bool', '=', True),
                             ('date', '=', programming_date)])
                        if old_closing_balance:
                            if new_opening_balance:
                                new_opening_balance.opening_balance = old_closing_balance.total
                                new_opening_balance.total = (
                                                                    new_opening_balance.opening_balance + new_opening_balance.debit) - new_opening_balance.credit
                            else:
                                self.env['cash.transfer.record.register'].create({
                                    'date': programming_date,
                                    'name': 'Opening Balance',
                                    'branch_id': self.env.user.branch_id.id,
                                    'company_id': self.env.user.company_id.id,
                                    'opening_balance': old_closing_balance.total,
                                    'total': old_closing_balance.total,
                                    'opening_bool': True,
                                    'status': 'open',
                                })
                        today_opening_balance = self.env['cash.transfer.record.register'].search(
                            [('branch_id', '=', self.env.user.branch_id.id), ('opening_bool', '=', True),
                             ('date', '=', programming_date)])
                        new_closing_balance = self.env['cash.transfer.record.register'].search(
                            [('branch_id', '=', self.env.user.branch_id.id), ('closing_bool', '=', True),
                             ('date', '=', programming_date)])
                        if new_closing_balance:
                            new_closing_balance.opening_balance = today_opening_balance.total
                            new_closing_balance.total = (
                                                                new_closing_balance.opening_balance + new_closing_balance.debit) - new_closing_balance.credit
                        else:
                            self.env['cash.transfer.record.register'].create({
                                'date': programming_date,
                                'name': 'Closing Balance',
                                'branch_id': self.env.user.branch_id.id,
                                'company_id': self.env.user.company_id.id,
                                'opening_balance': old_closing_balance.total,
                                'total': old_closing_balance.total,
                                'closing_bool': True,
                                'status': 'close',
                            })
                        programming_date_back = programming_date

                self.mamool_id = self.env['mamool.loading'].create({
                    'name': 'Mamool Vehicle Request ' + self.vehicle_req.name + ' For Vehicle No(' + self.vehicle_id.license_plate + ')',
                    'date': self.invoice_date,
                    'branch_id': self.env.user.branch_id.id,
                    'company_id': self.env.user.company_id.id,
                    'amount': lorry_mamool,
                    'type': 'mamool'
                }).id
            lorry_loading = loading_charge
            if lorry_loading:
                # company_payment_id = self.env['account.account'].search(
                #     [('name', '=', 'Cash'), ('company_id', '=', self.env.user.company_id.id)]).id
                # cash_id = self.env['account.journal'].search(
                #     [('name', '=', 'Cash'), ('company_id', '=', self.env.user.company_id.id)]).id
                #
                # journal_list_1 = []
                # journal_line_two = (0, 0, {
                #     'account_id': company_payment_id,
                #     'name': 'Loading Charge For Vehicle Request' + self.vehicle_req.name + ' For Vehicle No(' + t.vehicle_id.license_plate + ')',
                #     'debit': lorry_loading,
                # })
                # journal_list_1.append(journal_line_two)
                # journal_line_one = (0, 0, {
                #     'account_id': self.env['branch.account'].search(
                #         [('name', '=', self.env.user.branch_id.id)]).account_id.id,
                #     'name': 'Loading Charge For Vehicle Request ' + self.vehicle_req.name + ' For Vehicle No(' + t.vehicle_id.license_plate + ')',
                #     'credit': lorry_loading,
                # })
                # journal_list_1.append(journal_line_one)
                # journal_id_1 = self.env['account.move'].create({
                #     'date': datetime.now().date(),
                #     'ref': 'Loading Charge For Vehicle Request ' + self.vehicle_req.name + ' For Vehicle No(' + t.vehicle_id.license_plate + ')',
                #     'journal_id': cash_id,
                #     'line_ids': journal_list_1,
                # })
                # journal_id_1.action_post()

                # code for Cash Book Balancing
                opening_balance = self.env['cash.transfer.record.register'].search(
                    [('opening_bool', '=', True), ('date', '=', self.invoice_date)])
                if not opening_balance:
                    self.env['cash.transfer.record.register'].create({
                        'date': self.invoice_date,
                        'name': 'Opening Balance',
                        'branch_id': self.env.user.branch_id.id,
                        'company_id': self.env.user.company_id.id,
                        'opening_balance': 0,
                        'opening_bool': True,
                        'status': 'open',
                    })
                    self.env['cash.transfer.record.register'].create({
                        'date': self.invoice_date,
                        'name': 'Closing Balance',
                        'branch_id': self.env.user.branch_id.id,
                        'company_id': self.env.user.company_id.id,
                        'opening_balance': 0,
                        'closing_bool': True,
                        'status': 'close',
                    })

                self.loading_cash_id = self.env['cash.transfer.record.register'].create({
                    'date': self.invoice_date,
                    'name': 'Loading Charge For Vehicle Request ' + self.vehicle_req.name + ' For Vehicle No(' + self.vehicle_id.license_plate + ')',
                    'debit': lorry_loading,
                    'branch_id': self.env.user.branch_id.id,
                    'company_id': self.env.user.company_id.id,
                    'status': 'open',
                    'transactions': True,
                    'transaction_type': 'loading charge',
                }).id
                debit_cash = lorry_loading
                # if not opening_balance:
                closing_balance = self.env['cash.transfer.record.register'].search(
                    [('branch_id', '=', self.env.user.branch_id.id), ('closing_bool', '=', True),
                     ('date', '=', self.invoice_date)])
                if closing_balance:
                    closing_balance.credit = closing_balance.credit + debit_cash
                    closing_balance.total = closing_balance.total + debit_cash

                current_date = datetime.now(IST).date()
                day_lenght = (current_date - self.invoice_date).days
                if day_lenght != 0:
                    programming_date_back = self.invoice_date
                    for days in range(1, day_lenght + 1):
                        programming_date = self.invoice_date + relativedelta(days=days)
                        old_closing_balance = self.env['cash.transfer.record.register'].search(
                            [('branch_id', '=', self.env.user.branch_id.id), ('closing_bool', '=', True),
                             ('date', '=', programming_date_back)])
                        new_opening_balance = self.env['cash.transfer.record.register'].search(
                            [('branch_id', '=', self.env.user.branch_id.id), ('opening_bool', '=', True),
                             ('date', '=', programming_date)])
                        if old_closing_balance:
                            if new_opening_balance:
                                new_opening_balance.opening_balance = old_closing_balance.total
                                new_opening_balance.total = (
                                                                    new_opening_balance.opening_balance + new_opening_balance.debit) - new_opening_balance.credit
                            else:
                                self.env['cash.transfer.record.register'].create({
                                    'date': programming_date,
                                    'name': 'Opening Balance',
                                    'branch_id': self.env.user.branch_id.id,
                                    'company_id': self.env.user.company_id.id,
                                    'opening_balance': old_closing_balance.total,
                                    'total': old_closing_balance.total,
                                    'opening_bool': True,
                                    'status': 'open',
                                })
                        today_opening_balance = self.env['cash.transfer.record.register'].search(
                            [('branch_id', '=', self.env.user.branch_id.id), ('opening_bool', '=', True),
                             ('date', '=', programming_date)])
                        new_closing_balance = self.env['cash.transfer.record.register'].search(
                            [('branch_id', '=', self.env.user.branch_id.id), ('closing_bool', '=', True),
                             ('date', '=', programming_date)])
                        if new_closing_balance:
                            new_closing_balance.opening_balance = today_opening_balance.total
                            new_closing_balance.total = (
                                                                new_closing_balance.opening_balance + new_closing_balance.debit) - new_closing_balance.credit
                        else:
                            self.env['cash.transfer.record.register'].create({
                                'date': programming_date,
                                'name': 'Closing Balance',
                                'branch_id': self.env.user.branch_id.id,
                                'company_id': self.env.user.company_id.id,
                                'opening_balance': old_closing_balance.total,
                                'total': old_closing_balance.total,
                                'closing_bool': True,
                                'status': 'close',
                            })
                        programming_date_back = programming_date





        else:
            raise exceptions.UserError('Ton Not Satisfied')
