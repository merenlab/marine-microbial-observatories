# Contributing

This catalogue is only as good as the people who know these programs. Corrections are as
valuable as new records, and "this contact person left three years ago" is a genuinely
useful contribution.

There are three ways in. Pick whichever suits you, they are all equally valid and helpful.

## By email

If you would rather not use GitHub at all, write to meren@hifmb.de and describe the
change in whatever form is convenient. We will update our records based on your
suggestion, and credit you as the verifier (unless you don't want that).

You do not need to format anything. A sentence is fine.

## By issue form

The [issue forms](../../issues/new/choose) ask for the same information as a record, one
box at a time:

- **Propose a new program** (add a time series, expedition, or coordination network).
- **Correct an existing record** (anything wrong, out of date, or missing).

We will generate a pull request to correct the record, and merge it to the repo.

## By pull request

Every record on the website has an **Edit this record** link. It opens that record's YAML
file in GitHub's web editor and offers to open a pull request when you save. This is
convenient as you don't have to deal with cloning the repository or setting up anything
locally.

But if you are git- and/or terminal-savvy, you can work locally:

```sh
git clone git@github.com:merenlab/marine-microbial-observatories.git
cd marine-microbial-observatories
pip install -r requirements.txt

# edit files under data/, then:
python3 scripts/validate.py
```

This will list all the errors and warnings for existing or new YAML files based on our schema.
If you are happy with the changes, commit and push them to your fork, then open a pull request against the main repository. 

## Rules of thumb

**One record per file, one file per record.** `data/<type>/<id>.yml`. The filename must
match the record's `id` field; the validator enforces this.

**Ids are permanent.** An id is in URLs, in citations, and in other people's bookmarks.
Renaming a program is fine; changing its id is not, unless it is genuinely new.

**Update the verification block when you confirm something.** This is the field that makes
the catalogue trustworthy over time:

```yaml
verification:
  checked-by:
    - Your Name
  checked-on: 2026-08-04
```

Use `YYYY-MM-DD`. Please do not write `06/07/2026` to avoid any issues.

**Only add contacts who want to be contacted.** Their addresses appear on a public
website. If you are entering someone else's contact information, please ask first.

**Do not commit `dist/`.** It is regenerated on every push. It is already in `.gitignore`,
so there shouldn't be any problem there, but still.

**Add new vocabulary deliberately.** `status`, `sampling-depth`, `sampling-cadence`,
`omics-types` and `ocean-basins` are closed lists in the schema. If a program does not fit,
that is worth discussing in an issue rather than working around. In such a case either the
list needs extending (edit the schema in the same PR and say why) or the record needs rethinking.

**Prefer a bare DOI to a URL** in `publications`: I.e., `10.1038/s41467-025-56203-3`, and not
`https://doi.org/10.1038/...`, and certainly not a publisher landing page. The website builds the
link. Where no DOI exists, a URL is fine.

**Accessions are bare too.** `PRJEB43905`, not `ENA: PRJEB43905` or a browser URL. The
archive is inferred from the prefix.

## How do we do continuous integration checks

`.github/workflows/validate.yml` runs on every pull request.

**Errors block the merge:**

- a field the schema does not know about, or a missing required field
- a value outside a controlled vocabulary
- a malformed email address, URL, DOI or accession
- coordinates out of range, or an end year before a start year
- invisible Unicode characters (non-breaking spaces and zero-width spaces survive
  copy-paste from spreadsheets and silently break links and email addresses)
- a filename that disagrees with the record's `id`

**Warnings do not block anything**. They mark records with no verification date, no
accessions, no publications, missing coordinates, or contacts without an email. Many
records have warnings today; that is expected, and it should not stop you fixing something
unrelated. Run `python3 scripts/validate.py --strict` if you want warnings to fail locally.

## Licensing of what you contribute

This catalogue is licensed under [CC BY 4.0](LICENSE). By opening a pull request, filing an
issue with record content, or emailing us a correction, you agree that your contribution
goes in under the same licence, and that you have the right to contribute it.

In practice that means: describe programs in your own words, and do not paste in text that
someone else holds copyright over. Mission statements quoted from a network's own website
are fine and normal for the `mission-statement` field — attribute them in `notes` if the
wording is lifted verbatim. Abstracts copied out of papers are not; link the DOI instead.

## Questions

Open an issue, write an email to meren@hifmb.de. A question about the catalogue is a
contribution too :) If something was unclear to you, the documentation needs fixing.
