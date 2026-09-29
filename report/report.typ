#import "@preview/ilm:2.1.1": *

#set text(lang: "en")

#show: ilm.with(
  title: [A Comparative Evaluation of PostgreSQL, openGauss, and File-Based Data Processing],
  authors: "LI Yuanrui (12511921)",
  date: datetime.today(),
  abstract: [
    
  ],
  // preface: [
  //   #align(center + horizon)[
  //     Thank you for using this template #emoji.heart \
  //     I hope you like it #emoji.face.smile
  //   ]
  // ],
  bibliography: bibliography("refs.bib"),
  figure-index: (enabled: true),
  table-index: (enabled: true),
  listing-index: (enabled: true),
  raw-text: (
    font: ("JetBrains Mono")
  )
)

#set text(
  font: (
    (name: "libertinus serif", covers: "latin-in-cjk"),
    "Noto Serif CJK SC"
  )
)
#show smartquote: set text(font: "libertinus serif") 

= Heading 1