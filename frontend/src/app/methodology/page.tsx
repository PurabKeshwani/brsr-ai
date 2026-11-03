import Link from "next/link";
import { PageHead, Panel } from "@/components/workspace/Shared";
export default function MethodologyPage() {
  return (
    <div className="workspace-page">
      <PageHead
        title="Methodology"
        description="Interpret the score, comparison population and evidence before drawing conclusions."
      />
      <div className="analysis-grid">
        <Panel
          title="Transparency score"
          note="Disclosure quality, on a 0–100 scale."
        >
          <div className="formula">
            TS = 0.40 C + 0.30 Sp + 0.20 Cl + 0.10 G
          </div>
          <dl className="method-definitions">
            <dt>Completeness, C</dt>
            <dd>
              Percentage of distinct corpus concepts with accepted, nontrivial
              values in the report. The corpus denominator can grow when filings
              are added.
            </dd>
            <dt>Specificity, Sp</dt>
            <dd>
              Share of retained concept–text narrative pairs containing at least
              one KPI or evidence marker.
            </dd>
            <dt>Clarity, Cl</dt>
            <dd>
              100 minus the share flagged as vague by the configured combined
              detector. Clear wording alone does not establish concrete
              evidence.
            </dd>
            <dt>SDG breadth, G</dt>
            <dd>
              Share of 17 goals covered by the principle-to-goal mapping, using
              evidence-backed narrative disclosures. It measures coverage rather
              than goal achievement.
            </dd>
          </dl>
        </Panel>
        <Panel
          title="Four levels of comparison"
          note="The reporting hierarchy used in the paper’s results section."
        >
          <ol className="method-list">
            <li>
              <Link href="/companies">One company</Link>
              <p>
                Inspect the score calculation, concepts, source facts, assurance
                and review signals.
              </p>
            </li>
            <li>
              <Link href="/compare">Selected peers</Link>
              <p>
                Compare up to eight companies, with sector and reporting-period
                controls.
              </p>
            </li>
            <li>
              <Link href="/compare">Complete sector</Link>
              <p>
                Inspect every scored company, distribution, mean, median, range
                and standard deviation.
              </p>
            </li>
            <li>
              <Link href="/compare">All sectors</Link>
              <p>
                Compare the full scored population and sector groups. Five
                companies is the minimum used for reliable peer groups.
              </p>
            </li>
          </ol>
        </Panel>
        <Panel
          title="Reporting periods and time series"
          note="Keep cross-sectional and longitudinal comparisons separate."
        >
          <p>
            Company and sector comparisons use the saved latest-report score per
            CIN. Report periods are reconstructed from the database because the
            original score export did not retain report IDs. A period filter
            selects the corresponding latest-report subset; it does not recreate
            missing historical scores.
          </p>
          <p>
            The paired-year export contains eight companies with two scored
            reports. Changes refer to the same company at both endpoints. The
            available-case sample cannot establish a market-wide trend. Company
            metric history separately uses prior/current periods within the
            selected XBRL filing.
          </p>
          <Link className="text-action" href="/time-series">
            Open time series →
          </Link>
        </Panel>
        <Panel
          title="Evidence and greenwashing screening"
          note="Source text and numeric records support human review."
        >
          <p>
            Claim–number signals identify improvement language that conflicts
            with a filed numeric trend. Evidence or assurance gaps, lexical cues
            and silent removals are distinct review leads. They are not proof of
            deceptive intent.
          </p>
          <p>
            The evidence view retains the exact filed paragraph, highlighted
            matched sentence, concept, unit, period, dimensions and source fact
            IDs. The source register preserves original values. No PDF page
            number is invented when PDF coordinates are unavailable.
          </p>
          <p>
            Numeric metric series keep units and dimensional boundaries
            separate. Conflicting duplicates are excluded rather than summed.
            Percentage changes require a nonzero previous value.
          </p>
        </Panel>
      </div>
    </div>
  );
}
