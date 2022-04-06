from odoo import fields, models, api
from datetime import datetime, date
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT
import dateutil
import pytz
from dateutil.relativedelta import relativedelta

UTC = pytz.utc
IST = pytz.timezone('Asia/Kolkata')


class OpeningBalanceBranch(models.Model):
    _inherit = 'opening.balance.branch'

    def close_translation(self):
        for details in self.env['branch.account'].search([]):
            if datetime.now(IST).hour == 0:
                closing_id = self.env['cash.transfer.record.register'].search([('branch_id', '=', details.name.id),('date', '=', datetime.now(IST).date() - relativedelta(days=1)),('closing_bool', '=', True)])
                if closing_id.id:
                    closing_id.unlink()
                if not self.env['cash.transfer.record.register'].search([('branch_id', '=', details.name.id), ('date', '=', datetime.now(IST).date() - relativedelta(days=1)), ('closing_bool', '=', True)]):
                    cash_details = self.env['cash.transfer.record.register'].search(
                        [('branch_id', '=', details.name.id),
                         ('date', '=', datetime.now(IST).date() - relativedelta(days=1))])
                    start_cash = 0.0
                    debit = 0.0
                    credit = 0.0
                    for line in cash_details:
                        if line.opening_bool == True:
                            start_cash = line.total
                        else:
                            credit = credit + line.credit
                            debit = debit + line.debit
                    total = (start_cash + debit) - credit
                    self.env['cash.transfer.record.register'].create({
                        'name': 'Closing Balance',
                        'debit': debit,
                        'credit': credit,
                        'opening_balance': start_cash,
                        'total': total,
                        'closing_bool': True,
                        'date': datetime.now(IST).date() - relativedelta(days=1),
                        'branch_id': details.name.id,
                        'company_id': details.name.company_id.id,
                        'status': 'close'
                    })
                if not self.env['cash.transfer.record.register'].search([('branch_id', '=', details.name.id), (
                    'date', '=', datetime.now(IST).date()), ('opening_bool', '=', True)]):
                        cash_details = self.env['cash.transfer.record.register'].search(
                            [('branch_id', '=', details.name.id),
                             ('date', '=', datetime.now(IST).date() - relativedelta(days=1))])
                        start_cash = 0.0
                        debit = 0.0
                        credit = 0.0
                        for line in cash_details:
                            if line.opening_bool == True:
                                start_cash = line.total
                            else:
                                credit = credit + line.credit
                                debit = debit + line.debit
                        total = (start_cash + debit) - credit
                        self.env['cash.transfer.record.register'].create({
                            'name': 'Opening Balance',
                            'opening_balance': total,
                            'total': total,
                            'opening_bool': True,
                            'date': datetime.now(IST).date(),
                            'branch_id': details.name.id,
                            'company_id': details.name.company_id.id,
                            'next_opening': True
                        })
                    # cron_id = self.env['ir.cron'].sudo().search([('name','=','Account Closing Automatic')])
                    # print(cron_id)
                    # cron_id.sudo().update({
                    #     'nextcall':datetime.now().replace(hour=22)
                    # })
                    # print(cron_id.nextcall)