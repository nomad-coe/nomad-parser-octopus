package eu.nomad_lab.parsers

import org.specs2.mutable.Specification

object OctopusParserSpec extends Specification {
  "OctopusParserTest" >> {
    "test with json-events" >> {
      ParserRun.parse(OctopusParser, "parsers/octopus/test/examples/libvdwxc.quick.info", "json-events") must_== ParseResult.ParseSuccess
    }
    "test with json" >> {
      ParserRun.parse(OctopusParser, "parsers/octopus/test/examples/libvdwxc.quick.info", "json") must_== ParseResult.ParseSuccess
    }
  }
}
