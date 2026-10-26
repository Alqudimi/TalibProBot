import tg from 'k6/x/telegym';
import { check } from 'k6';

export const options = {
  scenarios: {
    user_journey: { executor: 'shared-iterations', vus: 1, iterations: 1, maxDuration: '60s' },
  },
  thresholds: { checks: ['rate>0.95'] },
};

export default function () {
  const u = tg.newUser(0);

  u.send('/help');
  const help = u.awaitText('دليل الاستخدام|الاستخدام', 10);
  check(help, { 'help reply arrived': (m) => m !== null });

  u.send('/edu');
  const edu = u.awaitText('مركز المذاكرة|التعلم الذاتي', 10);
  check(edu, {
    'study center arrived': (m) => m !== null,
    'study keyboard exists': (m) => m && m.replyMarkup !== null,
  });

  u.send('/daily');
  const daily = u.awaitText('السؤال|اختر الإجابة', 10);
  check(daily, { 'daily question arrived': (m) => m !== null });

  u.send('/support');
  const support = u.awaitText('الدعم|التذكرة', 10);
  check(support, { 'support center arrived': (m) => m !== null });

  u.send('/privacy');
  const privacy = u.awaitText('الخصوصية|إدارة بيانات', 10);
  check(privacy, { 'privacy center arrived': (m) => m !== null });
}
