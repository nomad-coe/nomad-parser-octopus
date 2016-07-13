package eu.nomad_lab.parsers

import org.specs2.mutable.Specification

object OctopusParserSpec extends Specification {
  "OctopusParserTest" >> {
    "test with json-events" >> {
      ParserRun.parse(OctopusParser, "parsers/octopus/test/examples/ink-gs/static/info", "json-events") must_== ParseResult.ParseSuccess
    }
    "test with json" >> {
      ParserRun.parse(OctopusParser, "parsers/octopus/test/examples/ink-gs/static/info", "json") must_== ParseResult.ParseSuccess
    }
    "test H2O with json-events" >> {
      ParserRun.parse(OctopusParser, "parsers/octopus/test/examples/H2O/static/info", "json-events") must_== ParseResult.ParseSuccess
    }
    "test H2O with json" >> {
      ParserRun.parse(OctopusParser, "parsers/octopus/test/examples/H2O/static/info", "json") must_== ParseResult.ParseSuccess
    }
    "test O2 with json-events" >> {
      ParserRun.parse(OctopusParser, "parsers/octopus/test/examples/O2/static/info", "json-events") must_== ParseResult.ParseSuccess
    }
    "test O2 with json" >> {
      ParserRun.parse(OctopusParser, "parsers/octopus/test/examples/O2/static/info", "json") must_== ParseResult.ParseSuccess
    }
    "test Si with json-events" >> {
      ParserRun.parse(OctopusParser, "parsers/octopus/test/examples/Si/static/info", "json-events") must_== ParseResult.ParseSuccess
    }
    "test Si with json" >> {
      ParserRun.parse(OctopusParser, "parsers/octopus/test/examples/Si/static/info", "json") must_== ParseResult.ParseSuccess
    }
    "test Fe with json-events" >> {
      ParserRun.parse(OctopusParser, "parsers/octopus/test/examples/Fe/static/info", "json-events") must_== ParseResult.ParseSuccess
    }
    "test Fe with json" >> {
      ParserRun.parse(OctopusParser, "parsers/octopus/test/examples/Fe/static/info", "json") must_== ParseResult.ParseSuccess
    }
  }
}
